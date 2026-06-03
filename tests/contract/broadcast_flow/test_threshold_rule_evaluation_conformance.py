"""Threshold rule-evaluation + three-implementer conformance (D142, D153, S57).

Two contract properties the parametrised BroadcastFlow scenarios do not
cover:

1. The two-stage chain hand-off: the ThresholdEvaluator, evaluating over
   calendar state, emits exactly the crossings the rules match (and none
   on no-match — the restraint property), and each emitted crossing's
   metadata round-trips into a ThresholdCrossing the threshold-briefing
   composes from. This binds the state-store-evaluation model (D153) and
   the emitter→briefing metadata contract at the contract tier.
2. The three-implementer BroadcastFlow set is complete (P15 close
   criterion 1): daily-briefing, threshold-briefing, ThresholdEvaluator
   all register against the harness.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from contexts.threshold_briefing.application.rule_config import phase_2a_rules
from contexts.threshold_briefing.application.threshold_evaluator import (
    ThresholdEvaluator,
)
from contexts.threshold_briefing.domain.crossing import ThresholdCrossing
from contexts.threshold_briefing.domain.meeting_state import MeetingState
from contexts.threshold_briefing.domain.threshold_rule import ThresholdRuleType
from shared_kernel.broadcast_flow import BroadcastTriggerType, TriggerContext

from tests.contract.broadcast_flow.conftest import (
    _REGISTRY,
    _load_registration_modules,
)

_TRIGGERED_AT = "2026-06-03T23:00:00+00:00"


def _at(hour: int) -> datetime:
    return datetime(2026, 6, 3, hour, 0, tzinfo=timezone.utc)


class _StateReader:
    def __init__(self, meetings: tuple[MeetingState, ...]) -> None:
        self._meetings = meetings

    async def list_meetings(self, *, actor: Any, include_cancelled: bool = True):
        return self._meetings


class _RecordingEmitter:
    def __init__(self) -> None:
        self.emitted: list[Any] = []

    async def emit(self, *, tenant_id, user_id, match, triggered_at) -> None:
        self.emitted.append(match)


def _meeting(title, *, status="confirmed", start=None, end=None, cancelled_at=None, eid=None):
    return MeetingState(
        google_event_id=eid or uuid4().hex,
        meeting_id=uuid4(),
        title=title,
        status=status,
        start_at=start,
        end_at=end,
        cancelled_at=cancelled_at,
    )


def _run_evaluator(meetings) -> _RecordingEmitter:
    emitter = _RecordingEmitter()
    evaluator = ThresholdEvaluator(
        state_reader=_StateReader(meetings),
        emitter=emitter,
        rules=phase_2a_rules(),
        jurisdiction="eu-west",
    )

    async def _drive():
        await evaluator.fire(
            tenant_id=uuid4(),
            user_id="op",
            trigger_context=TriggerContext(
                trigger_type=BroadcastTriggerType.SCHEDULED_EVALUATION,
                trigger_id=uuid4(),
                triggered_at=_TRIGGERED_AT,
            ),
        )

    asyncio.run(_drive())
    return emitter


def test_evaluator_emits_cancellation_crossing_that_round_trips_to_briefing() -> None:
    """A cancellation in state → one crossing whose metadata a briefing reads."""
    emitter = _run_evaluator(
        (_meeting("Board sync", status="cancelled", cancelled_at=_at(9), eid="evt-1"),)
    )
    assert len(emitter.emitted) == 1
    match = emitter.emitted[0]
    assert match.rule_type is ThresholdRuleType.MEETING_CANCELLED
    # The emitter→briefing metadata contract: the crossing round-trips.
    crossing = ThresholdCrossing.from_metadata(match.to_trigger_metadata())
    assert crossing.title == "Board sync"
    assert crossing.rule_type == "meeting_cancelled"
    assert crossing.crossing_identity == match.crossing_identity()


def test_evaluator_emits_conflict_crossing() -> None:
    emitter = _run_evaluator(
        (
            _meeting("A", start=_at(9), end=_at(11), eid="a"),
            _meeting("B", start=_at(10), end=_at(12), eid="b"),
        )
    )
    assert len(emitter.emitted) == 1
    assert emitter.emitted[0].rule_type is ThresholdRuleType.MEETING_CONFLICT


def test_evaluator_emits_nothing_on_no_cross_restraint() -> None:
    """The restraint property at the contract tier: no match → no emission."""
    emitter = _run_evaluator(
        (
            _meeting("A", start=_at(9), end=_at(10)),
            _meeting("B", start=_at(11), end=_at(12)),
        )
    )
    assert emitter.emitted == []


def test_three_broadcast_flow_implementers_registered() -> None:
    """P15 close criterion 1: the three-implementer BroadcastFlow set is complete."""
    _load_registration_modules()
    names = {f.name for f in _REGISTRY}
    assert {"daily_briefing", "threshold_briefing", "threshold_evaluator"} <= names
