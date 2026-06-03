"""Register the ThresholdEvaluator BroadcastFlow implementer (D142, D153, S57).

Registers the evaluator against the contract harness with stub consumer
ports (state-reader returning a cancelled meeting; recording emitter; no
refresh) so the parametrised conformance scenarios run it without a
database — verifying the fire signature, BroadcastFlow Protocol
satisfaction, and ThresholdEvaluationResponse satisfying CitedResponse.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from contexts.threshold_briefing.application.rule_config import phase_2a_rules
from contexts.threshold_briefing.application.threshold_evaluator import (
    ThresholdEvaluator,
)
from contexts.threshold_briefing.domain.meeting_state import MeetingState
from shared_kernel.broadcast_flow import BroadcastTriggerType, TriggerContext

from tests.contract.broadcast_flow.conftest import (
    BroadcastFlowImplementerFixture,
    register_broadcast_flow_implementer,
)


class _StubStateReader:
    async def list_meetings(self, *, actor: Any, include_cancelled: bool = True):
        return (
            MeetingState(
                google_event_id="evt-1",
                meeting_id=uuid4(),
                title="Board sync",
                status="cancelled",
                start_at=datetime(2026, 6, 3, 15, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 6, 3, 16, 0, tzinfo=timezone.utc),
                cancelled_at=datetime(2026, 6, 3, 9, 0, tzinfo=timezone.utc),
            ),
        )


class _StubEmitter:
    def __init__(self) -> None:
        self.emitted: list[Any] = []

    async def emit(self, *, tenant_id, user_id, match, triggered_at) -> None:
        self.emitted.append(match)


def _make_instance() -> ThresholdEvaluator:
    return ThresholdEvaluator(
        state_reader=_StubStateReader(),
        emitter=_StubEmitter(),
        rules=phase_2a_rules(),
        jurisdiction="eu-west",
    )


def _sample_trigger_context() -> TriggerContext:
    return TriggerContext(
        trigger_type=BroadcastTriggerType.SCHEDULED_EVALUATION,
        trigger_id=uuid4(),
        triggered_at="2026-06-03T23:00:00+00:00",
    )


register_broadcast_flow_implementer(
    BroadcastFlowImplementerFixture(
        name="threshold_evaluator",
        implementer_cls=ThresholdEvaluator,
        make_instance=_make_instance,
        handled_trigger_type=BroadcastTriggerType.SCHEDULED_EVALUATION,
        sample_trigger_context_factory=_sample_trigger_context,
    )
)
