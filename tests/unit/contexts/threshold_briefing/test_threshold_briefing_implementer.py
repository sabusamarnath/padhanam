"""Unit tests for the ThresholdBriefingImplementer (D153, S57)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from contexts.threshold_briefing.application.threshold_briefing_implementer import (
    ThresholdBriefingImplementer,
)
from contexts.threshold_briefing.domain.crossing import ThresholdCrossing
from contexts.threshold_briefing.domain.response import render_for_whatsapp
from contexts.threshold_briefing.domain.rule_match import RuleMatch
from contexts.threshold_briefing.domain.threshold_rule import ThresholdRuleType
from shared_kernel.broadcast_flow import (
    BroadcastFlow,
    BroadcastResponse,
    BroadcastTriggerType,
    TriggerContext,
)
from tests.unit.contexts.threshold_briefing.conftest import at


class _StubComposer:
    def __init__(self, prose: str = "Your board sync was cancelled.") -> None:
        self._prose = prose
        self.calls = 0

    async def compose(self, *, crossing: ThresholdCrossing) -> str:
        self.calls += 1
        return self._prose


class _FailingComposer:
    async def compose(self, *, crossing: ThresholdCrossing) -> str:
        raise RuntimeError("LLM down")


class _RecordingNotifier:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_briefing(self, *, actor: Any, body: str) -> None:
        self.sent.append(body)


def _cancel_match() -> RuleMatch:
    return RuleMatch(
        rule_id="calendar.meeting_cancelled",
        rule_type=ThresholdRuleType.MEETING_CANCELLED,
        google_event_id="evt-1",
        meeting_id=uuid4(),
        title="Board sync",
        summary="Meeting cancelled: Board sync",
        cancelled_at=at(9),
    )


def _trigger_for(match: RuleMatch) -> TriggerContext:
    return TriggerContext(
        trigger_type=BroadcastTriggerType.THRESHOLD_CROSSED,
        trigger_id=uuid4(),
        triggered_at=at(10).isoformat(),
        metadata=match.to_trigger_metadata(),
    )


def _fire(implementer, trigger) -> Any:
    async def _drive():
        return await implementer.fire(
            tenant_id=uuid4(), user_id="op", trigger_context=trigger
        )

    return asyncio.run(_drive())


def test_implementer_is_a_broadcast_flow() -> None:
    impl = ThresholdBriefingImplementer(
        composer=_StubComposer(), notifier=_RecordingNotifier(), jurisdiction="eu-west"
    )
    assert isinstance(impl, BroadcastFlow)


def test_fire_composes_sends_and_cites_the_meeting() -> None:
    composer = _StubComposer("Your board sync was cancelled.")
    notifier = _RecordingNotifier()
    match = _cancel_match()
    impl = ThresholdBriefingImplementer(
        composer=composer, notifier=notifier, jurisdiction="eu-west"
    )
    response = _fire(impl, _trigger_for(match))

    assert composer.calls == 1
    assert len(notifier.sent) == 1
    assert "board sync was cancelled" in notifier.sent[0].lower()
    assert isinstance(response, BroadcastResponse)
    assert response.text == "Your board sync was cancelled."
    assert len(response.cited_artefacts) == 1
    assert response.cited_artefacts[0].artefact_id == match.meeting_id
    assert response.cited_artefacts[0].artefact_type == "meeting"


def test_fire_falls_back_to_summary_on_composer_failure() -> None:
    notifier = _RecordingNotifier()
    match = _cancel_match()
    impl = ThresholdBriefingImplementer(
        composer=_FailingComposer(), notifier=notifier, jurisdiction="eu-west"
    )
    response = _fire(impl, _trigger_for(match))
    # The proactive heads-up still goes out, using the crossing summary.
    assert response.text == "Meeting cancelled: Board sync"
    assert len(notifier.sent) == 1


def test_render_carries_header_prose_and_citation() -> None:
    match = _cancel_match()
    impl = ThresholdBriefingImplementer(
        composer=_StubComposer("Board sync cancelled."),
        notifier=_RecordingNotifier(),
        jurisdiction="eu-west",
    )
    response = _fire(impl, _trigger_for(match))
    rendered = render_for_whatsapp(
        response, composed_at=datetime(2026, 6, 3, 10, 30, tzinfo=timezone.utc)
    )
    assert rendered.startswith("⚠ Heads-up")
    assert "Board sync cancelled." in rendered
    assert "ref " in rendered and "10:30 UTC" in rendered


def test_crossing_round_trips_through_metadata() -> None:
    match = _cancel_match()
    crossing = ThresholdCrossing.from_metadata(match.to_trigger_metadata())
    assert crossing.title == "Board sync"
    assert crossing.rule_type == "meeting_cancelled"
    assert crossing.meeting_id == match.meeting_id
    assert crossing.crossing_identity == match.crossing_identity()
