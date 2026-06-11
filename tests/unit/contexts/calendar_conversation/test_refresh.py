"""Unit tests for calendar-conversation background refresh (D178, revising D150).

The cell no longer blocks the open on a refresh. It serves the cached Meeting
store immediately — no synchronous wait, no staleness caveat — and kicks a
fire-and-forget refresh that updates the store for the next turn. A refresh
already in flight for the tenant is not re-kicked (dedup), and a background
failure never fails the turn.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest

from contexts.calendar_conversation.application import cell as cell_module
from contexts.calendar_conversation.application.cell import (
    CalendarConversationCell,
)
from contexts.calendar_conversation.application.ports.calendar_refresh import (
    CalendarRefreshError,
)
from contexts.messaging.adapters.threshold_single_pair import (
    SinglePairThresholdResolverAdapter,
)
from shared_kernel import (
    ConfidenceThresholds,
    ConversationInput,
    ConversationInvocation,
)
from tests.unit.contexts.calendar_conversation.conftest import make_meeting
from tests.unit.contexts.calendar_conversation.test_cell import (
    _FakeMeetingReader,
    _PendingStore,
    _StubAuditPort,
    _StubConfidence,
    _StubStructuredOutput,
    _actor,
)

_NOW = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _isolate_refresh_state():
    """Clear the process-global D178 refresh state around each test."""
    cell_module._INFLIGHT_REFRESH.clear()
    cell_module._BACKGROUND_TASKS.clear()
    yield
    cell_module._INFLIGHT_REFRESH.clear()
    cell_module._BACKGROUND_TASKS.clear()


class _RefreshOk:
    def __init__(self) -> None:
        self.calls = 0

    async def refresh(self, *, tenant_context: Any) -> None:
        self.calls += 1


class _RefreshGated:
    """Blocks inside refresh until released — proves the open does not wait."""

    def __init__(self) -> None:
        self.calls = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def refresh(self, *, tenant_context: Any) -> None:
        self.calls += 1
        self.started.set()
        await self.release.wait()


class _RefreshFails:
    def __init__(self) -> None:
        self.calls = 0

    async def refresh(self, *, tenant_context: Any) -> None:
        self.calls += 1
        raise CalendarRefreshError("nango unreachable")


def _cell(refresh_port):
    m = make_meeting(
        title="Board sync",
        start_at=datetime(2026, 6, 2, 15, 0, tzinfo=timezone.utc),
    )
    return CalendarConversationCell(
        structured_output_port=_StubStructuredOutput(
            {"intent_class": "find_by_date_range", "range_keyword": "today", "confidence": 0.95}
        ),
        meeting_reader=_FakeMeetingReader((m,)),
        actor=_actor(),
        confidence_calculator=_StubConfidence(),
        threshold_resolver=SinglePairThresholdResolverAdapter(
            thresholds=ConfidenceThresholds(high=0.8, medium=0.5),
        ),
        pending_clarification_reader=_PendingStore(),
        pending_clarification_repository=_PendingStore(),
        audit_port=_StubAuditPort(),
        refresh_port=refresh_port,
        originating_intake_id=uuid4(),
        clock=lambda: _NOW,
    )


async def _open_then_turn(cell):
    state = await cell.open(
        ConversationInvocation(purpose="calendar_query", actor_id="calendar-harness")
    )
    return await cell.turn(state, ConversationInput(text="what's on today?"))


def test_open_answers_from_cache_without_note() -> None:
    refresh = _RefreshOk()
    cell = _cell(refresh)

    async def _drive():
        state = await _open_then_turn(cell)
        # The refresh is backgrounded; drain it so the assertion is determinate.
        await cell._refresh_task
        return state.payload["calendar_response"]

    resp = asyncio.run(_drive())
    assert resp.staleness_note is None  # no caveat on the served turn
    assert resp.cited_artefacts  # answered from the store
    assert refresh.calls == 1  # the background refresh was kicked


def test_open_does_not_block_on_a_slow_refresh() -> None:
    refresh = _RefreshGated()
    cell = _cell(refresh)

    async def _drive():
        # If the open awaited the refresh it would hang on the gate; wait_for
        # converts that failure mode into a clear timeout instead of a hang.
        state = await asyncio.wait_for(_open_then_turn(cell), timeout=2.0)
        resp = state.payload["calendar_response"]
        assert resp.staleness_note is None
        # The turn returned with the refresh still outstanding — not awaited.
        assert not cell._refresh_task.done()
        refresh.release.set()
        await cell._refresh_task
        assert refresh.calls == 1
        return resp

    resp = asyncio.run(_drive())
    assert resp.cited_artefacts


def test_background_refresh_failure_does_not_fail_turn() -> None:
    refresh = _RefreshFails()
    cell = _cell(refresh)

    async def _drive():
        state = await _open_then_turn(cell)
        # Draining must not raise — the failure is swallowed inside the task.
        await cell._refresh_task
        return state.payload["calendar_response"]

    resp = asyncio.run(_drive())
    assert resp.staleness_note is None
    assert resp.cited_artefacts
    assert refresh.calls == 1


def test_inflight_refresh_is_not_restampeded() -> None:
    refresh = _RefreshGated()
    cell = _cell(refresh)

    async def _drive():
        state = await _open_then_turn(cell)  # kicks the (gated) refresh
        first_task = cell._refresh_task
        assert first_task is not None
        # A second turn while the first refresh is still in flight must not
        # kick another — the open is deduped on the tenant.
        state = await cell.turn(state, ConversationInput(text="what's on today?"))
        assert cell._refresh_task is None
        refresh.release.set()
        await first_task
        assert refresh.calls == 1  # exactly one sync, not two

    asyncio.run(_drive())
