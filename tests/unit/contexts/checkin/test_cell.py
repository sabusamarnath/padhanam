"""CheckinCell stage machine (D192, D194, S97b).

Exercises the two-stage flow with fake ports: the report stage parses and
transitions to confirm *without writing* (AC4), confirm writes and resolves,
cancel writes nothing, and the cell conforms to ConversationFlow structurally.
The real parser/writer adapters and their behaviour land in Commits 3/4.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles
from shared_kernel.conversation_flow import (
    ConversationClosure,
    ConversationFlow,
    ConversationInput,
    ConversationInvocation,
)

from contexts.messaging.api import PendingClarification
from contexts.messaging.domain.pending_clarification import (
    PendingClarificationStatus,
)

from contexts.checkin.application.cell import CheckinCell
from contexts.checkin.application.ports.checkin_writer import CheckinWriteResult
from contexts.checkin.domain.lever import EligibleLever
from contexts.checkin.domain.outcome import CheckinState, ParsedLeverOutcome

_TENANT = "11111111-1111-1111-1111-111111111111"
_USER = "operator"
_BEAT = "2026-06-15"

_LITANY = uuid4()
_VOICE = uuid4()


def _actor() -> ActorContext:
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id="t"
        ),
        actor_id=_USER,
        role_list=frozenset({ROLE_OPERATOR}),
        authorisation_set=authorisations_for_roles(frozenset({ROLE_OPERATOR})),
    )


def _levers() -> tuple[EligibleLever, ...]:
    return (
        EligibleLever(
            commitment_id=_LITANY, name="Litany", goal_id=_LITANY, goal_name="Litany"
        ),
        EligibleLever(
            commitment_id=_VOICE, name="Voice", goal_id=_VOICE, goal_name="Voice projection"
        ),
    )


def _pending(*, stage: str, parsed: list | None = None) -> PendingClarification:
    intent: dict = {
        "stage": stage,
        "beat_date": _BEAT,
        "levers": [lever.to_dict() for lever in _levers()],
    }
    if parsed is not None:
        intent["parsed"] = parsed
    now = datetime(2026, 6, 15, 20, 0, tzinfo=timezone.utc)
    return PendingClarification(
        id=uuid4(),
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        user_id=_USER,
        originating_channel="WHATSAPP",
        originating_user_address="whatsapp:+100",
        originating_intake_id=uuid4(),
        proposed_intent=intent,
        proposed_action_summary="check-in",
        status=PendingClarificationStatus.PENDING,
        target_cell="checkin",
        created_at=now,
        expires_at=now + timedelta(hours=24),
    )


class _StubPendingReader:
    def __init__(self, active: PendingClarification | None) -> None:
        self._active = active

    async def get_active(self, *, tenant_id, user_id):
        return self._active


class _StubPendingRepository:
    def __init__(self) -> None:
        self.saved: list[PendingClarification] = []
        self.status_updates: list[PendingClarification] = []

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


class _FakeParser:
    def __init__(self, outcomes: tuple[ParsedLeverOutcome, ...]) -> None:
        self.outcomes = outcomes
        self.calls: list[str] = []

    async def parse(self, *, reply_text, levers, actor):
        self.calls.append(reply_text)
        return self.outcomes


class _FakeWriter:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def write_outcomes(self, *, actor, outcomes, beat_date):
        self.calls.append((outcomes, beat_date))
        dids = sum(1 for o in outcomes if o.state is CheckinState.DID)
        didnts = sum(
            1 for o in outcomes if o.state is CheckinState.REPORTED_DIDNT
        )
        return CheckinWriteResult(
            dids_written=dids,
            reported_didnts_written=didnts,
            skipped_idempotent=0,
        )


def _run(coro):
    return asyncio.run(coro)


def _cell(*, active, parser, writer, repo, audit):
    return CheckinCell(
        reply_parser=parser,
        checkin_writer=writer,
        pending_clarification_reader=_StubPendingReader(active),
        pending_clarification_repository=repo,
        audit_port=audit,
        actor=_actor(),
        clock=lambda: datetime(2026, 6, 16, 1, 0, tzinfo=timezone.utc),
    )


def test_cell_conforms_to_conversation_flow() -> None:
    cell = _cell(
        active=None,
        parser=_FakeParser(()),
        writer=_FakeWriter(),
        repo=_StubPendingRepository(),
        audit=_StubAuditPort(),
    )
    assert isinstance(cell, ConversationFlow)


def test_report_stage_parses_and_transitions_without_writing() -> None:
    parser = _FakeParser(
        (
            ParsedLeverOutcome(commitment_id=_LITANY, state=CheckinState.DID),
            ParsedLeverOutcome(
                commitment_id=_VOICE, state=CheckinState.REPORTED_DIDNT
            ),
        )
    )
    writer = _FakeWriter()
    repo = _StubPendingRepository()
    cell = _cell(
        active=_pending(stage="awaiting_report"),
        parser=parser,
        writer=writer,
        repo=repo,
        audit=_StubAuditPort(),
    )
    state = _run(cell.open(ConversationInvocation(purpose="daily_checkin", actor_id=_USER)))
    state = _run(
        cell.turn(state, ConversationInput(text="did litany, missed voice"))
    )

    reply = state.payload["checkin_reply"]
    assert "Logging today" in reply
    assert "Litany: done" in reply
    assert "Voice projection: not done" in reply
    # No write before confirm (AC4).
    assert writer.calls == []
    # A new awaiting_confirm pending was created.
    assert repo.saved, "expected a new pending to be saved"
    assert repo.saved[-1].proposed_intent["stage"] == "awaiting_confirm"
    assert len(repo.saved[-1].proposed_intent["parsed"]) == 2


def test_confirm_writes_with_scheduled_beat_day_and_resolves() -> None:
    parsed = [
        ParsedLeverOutcome(
            commitment_id=_LITANY, state=CheckinState.DID
        ).to_dict(),
        ParsedLeverOutcome(
            commitment_id=_VOICE, state=CheckinState.REPORTED_DIDNT
        ).to_dict(),
    ]
    writer = _FakeWriter()
    repo = _StubPendingRepository()
    active = _pending(stage="awaiting_confirm", parsed=parsed)
    cell = _cell(
        active=active,
        parser=_FakeParser(()),
        writer=writer,
        repo=repo,
        audit=_StubAuditPort(),
    )
    state = _run(cell.open(ConversationInvocation(purpose="daily_checkin", actor_id=_USER)))
    state = _run(cell.turn(state, ConversationInput(text="yes")))

    assert len(writer.calls) == 1
    outcomes, beat_date = writer.calls[0]
    # Day attribution is the scheduled beat day, not the 01:00 reply clock.
    assert beat_date == date(2026, 6, 15)
    assert len(outcomes) == 2
    # The pending was resolved (status update emitted).
    assert any(
        p.status == PendingClarificationStatus.RESOLVED
        for p in repo.status_updates
    )
    assert "Logged" in state.payload["checkin_reply"]


def test_cancel_writes_nothing() -> None:
    writer = _FakeWriter()
    repo = _StubPendingRepository()
    active = _pending(stage="awaiting_confirm", parsed=[])
    cell = _cell(
        active=active,
        parser=_FakeParser(()),
        writer=writer,
        repo=repo,
        audit=_StubAuditPort(),
    )
    state = _run(cell.open(ConversationInvocation(purpose="daily_checkin", actor_id=_USER)))
    state = _run(cell.turn(state, ConversationInput(text="cancel")))

    assert writer.calls == []
    assert "nothing logged" in state.payload["checkin_reply"].lower()
