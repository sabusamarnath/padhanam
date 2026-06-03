"""Unit tests for the ThresholdEvaluator BroadcastFlow implementer (D153, S57)."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from contexts.threshold_briefing.application.ports.active_rule_refresh import (
    ActiveRuleRefreshError,
)
from contexts.threshold_briefing.application.rule_config import phase_2a_rules
from contexts.threshold_briefing.application.threshold_evaluator import (
    ThresholdEvaluator,
)
from contexts.threshold_briefing.domain.meeting_state import MeetingState
from shared_kernel.broadcast_flow import (
    BroadcastFlow,
    BroadcastResponse,
    BroadcastTriggerType,
    TriggerContext,
)
from tests.unit.contexts.threshold_briefing.conftest import at, make_meeting

_TENANT = uuid4()
_TRIGGERED_AT = at(23).isoformat()


class _StubStateReader:
    def __init__(self, meetings: tuple[MeetingState, ...]) -> None:
        self._meetings = meetings
        self.calls = 0

    async def list_meetings(
        self, *, actor: Any, include_cancelled: bool = True
    ) -> tuple[MeetingState, ...]:
        self.calls += 1
        return self._meetings


class _RecordingEmitter:
    def __init__(self) -> None:
        self.emitted: list[Any] = []

    async def emit(self, *, tenant_id, user_id, match, triggered_at) -> None:
        self.emitted.append(match)


class _RefreshSpy:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self._fail = fail
        self.order: list[str] = []

    async def refresh(self, *, tenant_context: Any) -> None:
        self.calls += 1
        if self._fail:
            raise ActiveRuleRefreshError("calendar unreachable")


def _evaluator(meetings, emitter, *, refresh_port=None, state_reader=None):
    return ThresholdEvaluator(
        state_reader=state_reader or _StubStateReader(meetings),
        emitter=emitter,
        rules=phase_2a_rules(),
        jurisdiction="eu-west",
        refresh_port=refresh_port,
    )


def _fire(evaluator) -> Any:
    async def _drive():
        return await evaluator.fire(
            tenant_id=_TENANT,
            user_id="op",
            trigger_context=TriggerContext(
                trigger_type=BroadcastTriggerType.SCHEDULED_EVALUATION,
                trigger_id=uuid4(),
                triggered_at=_TRIGGERED_AT,
            ),
        )

    return asyncio.run(_drive())


def test_evaluator_is_a_broadcast_flow() -> None:
    assert isinstance(_evaluator((), _RecordingEmitter()), BroadcastFlow)


def test_fire_emits_threshold_crossed_on_match() -> None:
    meetings = (
        make_meeting(title="Board sync", status="cancelled", cancelled_at=at(9)),
    )
    emitter = _RecordingEmitter()
    response = _fire(_evaluator(meetings, emitter))
    assert len(emitter.emitted) == 1
    assert emitter.emitted[0].title == "Board sync"
    assert isinstance(response, BroadcastResponse)
    assert response.crossed
    assert len(response.cited_artefacts) == 1
    assert response.cited_artefacts[0].artefact_type == "meeting"


def test_fire_emits_nothing_on_no_cross() -> None:
    """Restraint at the implementer: no match → no emission, empty response."""
    meetings = (
        make_meeting(title="A", status="confirmed", start_at=at(9), end_at=at(10)),
    )
    emitter = _RecordingEmitter()
    response = _fire(_evaluator(meetings, emitter))
    assert emitter.emitted == []
    assert not response.crossed
    assert response.cited_artefacts == ()


def test_fire_without_refresh_port_skips_refresh() -> None:
    emitter = _RecordingEmitter()
    # No refresh port wired: fire still evaluates over the (last-synced) state.
    state = _StubStateReader(())
    _fire(_evaluator((), emitter, state_reader=state))
    assert state.calls == 1


def test_fire_refresh_failure_still_evaluates_over_state() -> None:
    """A refresh that cannot complete is swallowed; the scan proceeds (D153)."""
    meetings = (
        make_meeting(title="Board sync", status="cancelled", cancelled_at=at(9)),
    )
    emitter = _RecordingEmitter()
    refresh = _RefreshSpy(fail=True)
    state = _StubStateReader(meetings)
    response = _fire(
        _evaluator(meetings, emitter, refresh_port=refresh, state_reader=state)
    )
    assert refresh.calls == 1  # refresh attempted
    assert state.calls == 1  # state still read
    assert response.crossed  # crossing still emitted


def test_fire_refreshes_before_reading_state() -> None:
    """Refresh-then-evaluate ordering: refresh is called before the state read."""
    order: list[str] = []

    class _OrderedRefresh:
        async def refresh(self, *, tenant_context: Any) -> None:
            order.append("refresh")

    class _OrderedState:
        async def list_meetings(self, *, actor: Any, include_cancelled: bool = True):
            order.append("read")
            return ()

    evaluator = ThresholdEvaluator(
        state_reader=_OrderedState(),
        emitter=_RecordingEmitter(),
        rules=phase_2a_rules(),
        jurisdiction="eu-west",
        refresh_port=_OrderedRefresh(),
    )
    _fire(evaluator)
    assert order == ["refresh", "read"]
