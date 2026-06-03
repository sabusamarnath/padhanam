"""Register the threshold-briefing BroadcastFlow implementer (D142, D153, S57).

Registers the briefing against the contract harness with stub consumer
ports (composer; recording notifier) and a sample THRESHOLD_CROSSED
trigger carrying a real crossing's metadata, so the parametrised
conformance scenarios run it without a database — verifying the fire
signature, BroadcastFlow Protocol satisfaction, and ThresholdBriefingResponse
satisfying CitedResponse.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from contexts.threshold_briefing.application.threshold_briefing_implementer import (
    ThresholdBriefingImplementer,
)
from contexts.threshold_briefing.domain.crossing import ThresholdCrossing
from contexts.threshold_briefing.domain.rule_match import RuleMatch
from contexts.threshold_briefing.domain.threshold_rule import ThresholdRuleType
from shared_kernel.broadcast_flow import BroadcastTriggerType, TriggerContext

from tests.contract.broadcast_flow.conftest import (
    BroadcastFlowImplementerFixture,
    register_broadcast_flow_implementer,
)


class _StubComposer:
    async def compose(self, *, crossing: ThresholdCrossing) -> str:
        return f"Heads-up: {crossing.summary}"


class _StubNotifier:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_briefing(self, *, actor: Any, body: str) -> None:
        self.sent.append(body)


def _make_instance() -> ThresholdBriefingImplementer:
    return ThresholdBriefingImplementer(
        composer=_StubComposer(),
        notifier=_StubNotifier(),
        jurisdiction="eu-west",
    )


def _sample_trigger_context() -> TriggerContext:
    match = RuleMatch(
        rule_id="calendar.meeting_cancelled",
        rule_type=ThresholdRuleType.MEETING_CANCELLED,
        google_event_id="evt-1",
        meeting_id=uuid4(),
        title="Board sync",
        summary="Meeting cancelled: Board sync",
    )
    return TriggerContext(
        trigger_type=BroadcastTriggerType.THRESHOLD_CROSSED,
        trigger_id=uuid4(),
        triggered_at="2026-06-03T10:00:00+00:00",
        metadata=match.to_trigger_metadata(),
    )


register_broadcast_flow_implementer(
    BroadcastFlowImplementerFixture(
        name="threshold_briefing",
        implementer_cls=ThresholdBriefingImplementer,
        make_instance=_make_instance,
        handled_trigger_type=BroadcastTriggerType.THRESHOLD_CROSSED,
        sample_trigger_context_factory=_sample_trigger_context,
    )
)
