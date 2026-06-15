"""The idempotent three-state check-in write (D192, S97b, Commit 4).

Fake-repository unit coverage of the split + idempotency; the live-DB proof
(the 0039 unique index, ON CONFLICT) is verified separately against the running
tenant. ``did`` -> completion (single did-source), not-done -> checkin response,
both guarded by an exists-by-beat-day check so a re-run does not double-write.
"""

from __future__ import annotations

import asyncio
from datetime import date
from uuid import UUID, uuid4

from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles

from contexts.daily_driver.application.log_checkin_outcomes import (
    CheckinOutcomeInput,
    log_checkin_outcomes,
)

_TENANT = "00000000-0000-4000-8000-00000000d001"
_BEAT = date(2026, 6, 15)
_A = uuid4()
_B = uuid4()


def _actor() -> ActorContext:
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id="t"
        ),
        actor_id="operator",
        role_list=frozenset({ROLE_OPERATOR}),
        authorisation_set=authorisations_for_roles(frozenset({ROLE_OPERATOR})),
    )


class _FakeRepo:
    def __init__(self) -> None:
        self.completions: list[tuple[UUID, date]] = []
        self.responses: list[tuple[UUID, date]] = []

    async def completion_exists_on_day(
        self, *, tenant_context, commitment_id, day
    ) -> bool:
        return (commitment_id, day) in self.completions

    async def add_completion(self, *, tenant_context, completion) -> None:
        self.completions.append(
            (completion.commitment_id, completion.completed_at.date())
        )

    async def checkin_response_exists_on_day(
        self, *, tenant_context, commitment_id, beat_date
    ) -> bool:
        return (commitment_id, beat_date) in self.responses

    async def add_checkin_response(self, *, tenant_context, response) -> None:
        self.responses.append((response.commitment_id, response.beat_date))


def _run(coro):
    return asyncio.run(coro)


def test_split_did_to_completion_didnt_to_response_silence_neither() -> None:
    repo = _FakeRepo()
    counts = _run(
        log_checkin_outcomes(
            repository=repo,
            actor=_actor(),
            outcomes=(
                CheckinOutcomeInput(commitment_id=_A, did=True),
                CheckinOutcomeInput(commitment_id=_B, did=False),
            ),
            beat_date=_BEAT,
        )
    )
    assert counts.dids_written == 1
    assert counts.reported_didnts_written == 1
    assert counts.skipped_idempotent == 0
    # did -> completion store only; didnt -> response store only.
    assert repo.completions == [(_A, _BEAT)]
    assert repo.responses == [(_B, _BEAT)]


def test_completion_stamped_to_scheduled_beat_day() -> None:
    repo = _FakeRepo()
    _run(
        log_checkin_outcomes(
            repository=repo,
            actor=_actor(),
            outcomes=(CheckinOutcomeInput(commitment_id=_A, did=True),),
            beat_date=_BEAT,
        )
    )
    # Stored completion's date is the scheduled beat day (noon-UTC stamp).
    assert repo.completions[0][1] == _BEAT


def test_idempotent_on_tenant_commitment_beat_day() -> None:
    repo = _FakeRepo()
    outcomes = (
        CheckinOutcomeInput(commitment_id=_A, did=True),
        CheckinOutcomeInput(commitment_id=_B, did=False),
    )
    first = _run(
        log_checkin_outcomes(
            repository=repo, actor=_actor(), outcomes=outcomes, beat_date=_BEAT
        )
    )
    second = _run(
        log_checkin_outcomes(
            repository=repo, actor=_actor(), outcomes=outcomes, beat_date=_BEAT
        )
    )
    assert (first.dids_written, first.reported_didnts_written) == (1, 1)
    # Re-confirm writes nothing new — both skip.
    assert (second.dids_written, second.reported_didnts_written) == (0, 0)
    assert second.skipped_idempotent == 2
    assert len(repo.completions) == 1
    assert len(repo.responses) == 1
