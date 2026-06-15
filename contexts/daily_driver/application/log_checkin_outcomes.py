"""log_checkin_outcomes — the idempotent three-state check-in write (D192, S97b).

The write splits by state and is idempotent on ``(tenant, commitment, beat
day)``: a ``did`` appends one ``CommitmentCompletion`` stamped to the scheduled
beat day (the single did-source — never the negative store); a not-done appends
one ``CheckinResponse`` with ``outcome=REPORTED_DIDNT`` for the beat day;
silence never reaches here (the parser omits an unmentioned lever). Each write
is guarded by an exists-by-beat-day check so a re-confirm or duplicate reply
does not double-write; the negative store also carries a unique-index backstop
(migration 0039).

The completion is stamped at **noon UTC** of the beat day so the cadence read's
date comparison lands on the scheduled day regardless of the operator's
timezone — the injectable-clock principle carried across the round-trip (day
attribution fixed at compose, not minted at confirm).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from uuid import UUID, uuid4

from shared_kernel import ActorContext

from contexts.daily_driver.domain.commitment import (
    CheckinOutcome,
    CheckinResponse,
    CommitmentCompletion,
)
from contexts.daily_driver.ports.commitment_repository import (
    CommitmentRepository,
)


@dataclass(frozen=True)
class CheckinOutcomeInput:
    """One per-commitment outcome to persist (``did`` True = a completion)."""

    commitment_id: UUID
    did: bool


@dataclass(frozen=True)
class CheckinWriteCounts:
    """What the write actually persisted (idempotent skips counted separately)."""

    dids_written: int
    reported_didnts_written: int
    skipped_idempotent: int


def _completed_at_for(beat_date: date) -> datetime:
    return datetime.combine(beat_date, time(hour=12), tzinfo=timezone.utc)


async def log_checkin_outcomes(
    *,
    repository: CommitmentRepository,
    actor: ActorContext,
    outcomes: tuple[CheckinOutcomeInput, ...],
    beat_date: date,
) -> CheckinWriteCounts:
    """Persist the three-state outcomes for ``beat_date``, idempotently."""
    tenant_context = actor.tenant_context
    tenant_uuid = UUID(tenant_context.tenant_id)
    dids = 0
    didnts = 0
    skipped = 0

    for outcome in outcomes:
        if outcome.did:
            already = await repository.completion_exists_on_day(
                tenant_context=tenant_context,
                commitment_id=outcome.commitment_id,
                day=beat_date,
            )
            if already:
                skipped += 1
                continue
            await repository.add_completion(
                tenant_context=tenant_context,
                completion=CommitmentCompletion(
                    id=uuid4(),
                    commitment_id=outcome.commitment_id,
                    tenant_id=tenant_uuid,
                    jurisdiction=tenant_context.jurisdiction,
                    completed_at=_completed_at_for(beat_date),
                ),
            )
            dids += 1
        else:
            already = await repository.checkin_response_exists_on_day(
                tenant_context=tenant_context,
                commitment_id=outcome.commitment_id,
                beat_date=beat_date,
            )
            if already:
                skipped += 1
                continue
            await repository.add_checkin_response(
                tenant_context=tenant_context,
                response=CheckinResponse(
                    id=uuid4(),
                    commitment_id=outcome.commitment_id,
                    tenant_id=tenant_uuid,
                    jurisdiction=tenant_context.jurisdiction,
                    beat_date=beat_date,
                    outcome=CheckinOutcome.REPORTED_DIDNT,
                ),
            )
            didnts += 1

    return CheckinWriteCounts(
        dids_written=dids,
        reported_didnts_written=didnts,
        skipped_idempotent=skipped,
    )


__all__ = [
    "CheckinOutcomeInput",
    "CheckinWriteCounts",
    "log_checkin_outcomes",
]
