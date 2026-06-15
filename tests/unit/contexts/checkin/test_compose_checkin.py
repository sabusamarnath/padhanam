"""The daily check-in composer (D192, D194, S97b, Commit 2).

Verifies eligibility -> goal-level message -> pending creation to the send
boundary with fakes: the message lists goal-level labels, the pending opens at
awaiting_report carrying the beat day + levers, and an empty eligible set sends
nothing. The live eligibility query is verified separately against live data.
"""

from __future__ import annotations

import asyncio
from datetime import date
from uuid import UUID, uuid4

from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles

from contexts.messaging.domain.pending_clarification import (
    PendingClarificationStatus,
)

from contexts.checkin.application.compose_checkin import compose_daily_checkin
from contexts.checkin.domain.lever import EligibleLever

_TENANT = "00000000-0000-4000-8000-00000000d001"
_BEAT = date(2026, 6, 15)
_HEALTH = uuid4()
_LITANY = uuid4()


def _actor() -> ActorContext:
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id="t"
        ),
        actor_id="operator",
        role_list=frozenset({ROLE_OPERATOR}),
        authorisation_set=authorisations_for_roles(frozenset({ROLE_OPERATOR})),
    )


def _levers() -> tuple[EligibleLever, ...]:
    return (
        EligibleLever(
            commitment_id=uuid4(), name="Lansoprazole", goal_id=_HEALTH,
            goal_name="Health regimen",
        ),
        EligibleLever(
            commitment_id=uuid4(), name="Aspirin", goal_id=_HEALTH,
            goal_name="Health regimen",
        ),
        EligibleLever(
            commitment_id=_LITANY, name="Litany", goal_id=_LITANY,
            goal_name="Litany",
        ),
    )


class _FakeEligibility:
    def __init__(self, levers: tuple[EligibleLever, ...]) -> None:
        self._levers = levers

    async def list_eligible(self, *, actor):
        return self._levers


class _FakeSender:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, *, actor, body: str) -> None:
        self.sent.append(body)


class _StubPendingRepository:
    def __init__(self) -> None:
        self.saved: list = []
        self.status_updates: list = []

    async def save(self, *, tenant_context, pending) -> None:
        self.saved.append(pending)

    async def update_status(self, *, tenant_context, pending) -> None:
        self.status_updates.append(pending)

    async def get_by_id(self, *, tenant_context, pending_id):
        return None

    async def get_active_for_user(self, *, tenant_context, user_id):
        return None


class _StubAuditPort:
    def __init__(self) -> None:
        self.emitted: list = []

    async def emit(self, event) -> None:
        self.emitted.append(event)


def _run(coro):
    return asyncio.run(coro)


def test_composer_sends_goal_level_prompt_and_opens_pending() -> None:
    sender = _FakeSender()
    repo = _StubPendingRepository()
    result = _run(
        compose_daily_checkin(
            eligible_levers_reader=_FakeEligibility(_levers()),
            message_sender=sender,
            pending_repository=repo,
            audit_port=_StubAuditPort(),
            actor=_actor(),
            beat_date=_BEAT,
            originating_user_address="whatsapp:+100",
        )
    )
    assert result.sent is True
    assert result.lever_count == 3
    assert result.goal_count == 2  # Health regimen (2 levers) + Litany
    # Goal-level message: Health regimen once, no clinical lever names.
    body = sender.sent[0]
    assert "Health regimen" in body
    assert "Litany" in body
    assert "Lansoprazole" not in body and "Aspirin" not in body
    assert "What did you get to?" in body
    # Pending opened at awaiting_report carrying the beat day + the 3 levers.
    pending = repo.saved[-1]
    assert pending.target_cell == "checkin"
    assert pending.status == PendingClarificationStatus.PENDING
    assert pending.proposed_intent["stage"] == "awaiting_report"
    assert pending.proposed_intent["beat_date"] == "2026-06-15"
    assert len(pending.proposed_intent["levers"]) == 3


def test_composer_sends_nothing_when_no_eligible_levers() -> None:
    sender = _FakeSender()
    repo = _StubPendingRepository()
    result = _run(
        compose_daily_checkin(
            eligible_levers_reader=_FakeEligibility(()),
            message_sender=sender,
            pending_repository=repo,
            audit_port=_StubAuditPort(),
            actor=_actor(),
            beat_date=_BEAT,
            originating_user_address="whatsapp:+100",
        )
    )
    assert result.sent is False
    assert sender.sent == []
    assert repo.saved == []
