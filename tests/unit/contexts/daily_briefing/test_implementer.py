"""Unit tests for the daily-briefing BroadcastFlow implementer (D142, D146, S54).

Exercises the five-step fire flow with stub ports: an activity-rich
day (reads return records/events/cases; the response cites all three)
and an empty day (no recent activity; the response cites only the
active cases; the briefing still sends).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from contexts.daily_briefing.application.daily_briefing_implementer import (
    DailyBriefingImplementer,
)
from contexts.daily_briefing.application.ports.daily_briefing_composer import (
    DailyBriefingComposedContent,
)
from contexts.daily_briefing.application.ports.daily_briefing_reader import (
    DailyBriefingAuditEvent,
    DailyBriefingCase,
    DailyBriefingIntakeRecord,
)
from contexts.daily_briefing.domain.response import DailyBriefingResponse
from shared_kernel import ActorContext
from shared_kernel.broadcast_flow import BroadcastTriggerType, TriggerContext


@dataclass
class _StubReader:
    intakes: tuple = ()
    events: tuple = ()
    cases: tuple = ()
    seen_actors: list = field(default_factory=list)

    async def read_intake_records(self, *, actor, window):  # noqa: ANN001
        self.seen_actors.append(actor)
        return self.intakes

    async def read_audit_events(self, *, actor, window):  # noqa: ANN001
        return self.events

    async def read_active_cases(self, *, actor):  # noqa: ANN001
        return self.cases


@dataclass
class _StubComposer:
    narrative: str = "the briefing prose"
    seen_inputs: list = field(default_factory=list)

    async def compose(
        self, *, briefing_period, intake_records, audit_events, active_cases  # noqa: ANN001
    ) -> DailyBriefingComposedContent:
        self.seen_inputs.append((intake_records, audit_events, active_cases))
        return DailyBriefingComposedContent(prose_narrative=self.narrative)


@dataclass
class _StubNotifier:
    sent: list = field(default_factory=list)

    async def send_briefing(self, *, actor: ActorContext, body: str) -> None:
        self.sent.append((actor, body))


def _context() -> TriggerContext:
    return TriggerContext(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED,
        trigger_id=uuid4(),
        triggered_at="2026-05-28T06:00:00+00:00",
    )


def _intake() -> DailyBriefingIntakeRecord:
    return DailyBriefingIntakeRecord(
        intake_id=uuid4(),
        intake_source="WHATSAPP_INBOUND",
        summary="logged something",
        created_at=datetime(2026, 5, 28, 5, 0, tzinfo=timezone.utc),
    )


def _event() -> DailyBriefingAuditEvent:
    return DailyBriefingAuditEvent(
        event_id=uuid4(),
        action_verb="portfolio.case.create",
        resource_type="case",
        resource_id=str(uuid4()),
        timestamp=datetime(2026, 5, 28, 5, 30, tzinfo=timezone.utc),
    )


def _case() -> DailyBriefingCase:
    return DailyBriefingCase(
        case_id=uuid4(),
        title="Q3 review",
        status="OPEN",
        created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )


def test_activity_rich_day_cites_all_three_sources() -> None:
    intake, event, case = _intake(), _event(), _case()
    reader = _StubReader(intakes=(intake,), events=(event,), cases=(case,))
    composer = _StubComposer(narrative="One new item against 1 case.")
    notifier = _StubNotifier()
    impl = DailyBriefingImplementer(
        reader=reader,
        composer=composer,
        notifier=notifier,
        jurisdiction="eu-west",
        window_hours=24,
    )

    response = asyncio.run(
        impl.fire(
            tenant_id=uuid4(),
            user_id="operator-001",
            trigger_context=_context(),
        )
    )

    assert isinstance(response, DailyBriefingResponse)
    assert response.text == "One new item against 1 case."
    assert response.cited_intake_records == (intake.intake_id,)
    assert response.cited_audit_events == (event.event_id,)
    assert len(response.cited_artefacts) == 1
    assert response.cited_artefacts[0].artefact_id == case.case_id
    assert response.cited_artefacts[0].artefact_type == "case"
    # the briefing sent once
    assert len(notifier.sent) == 1
    sent_actor, sent_body = notifier.sent[0]
    assert sent_actor.actor_id == "operator-001"
    assert "Daily briefing" in sent_body


def test_empty_day_still_sends_with_portfolio_only_citations() -> None:
    case = _case()
    reader = _StubReader(intakes=(), events=(), cases=(case,))
    composer = _StubComposer(
        narrative="Nothing changed in the last day; 1 active case."
    )
    notifier = _StubNotifier()
    impl = DailyBriefingImplementer(
        reader=reader,
        composer=composer,
        notifier=notifier,
        jurisdiction="eu-west",
        window_hours=24,
    )

    response = asyncio.run(
        impl.fire(
            tenant_id=uuid4(),
            user_id="operator-001",
            trigger_context=_context(),
        )
    )

    assert response.cited_intake_records == ()
    assert response.cited_audit_events == ()
    assert len(response.cited_artefacts) == 1  # active case only
    assert len(notifier.sent) == 1  # always-send (D146)


def test_window_derives_from_trigger_and_window_hours() -> None:
    reader = _StubReader(cases=(_case(),))
    impl = DailyBriefingImplementer(
        reader=reader,
        composer=_StubComposer(),
        notifier=_StubNotifier(),
        jurisdiction="eu-west",
        window_hours=24,
    )
    response = asyncio.run(
        impl.fire(
            tenant_id=uuid4(),
            user_id="operator-001",
            trigger_context=_context(),
        )
    )
    period = response.briefing_period
    assert period.window_end == datetime(
        2026, 5, 28, 6, 0, tzinfo=timezone.utc
    )
    assert (period.window_end - period.window_start).total_seconds() == 24 * 3600
