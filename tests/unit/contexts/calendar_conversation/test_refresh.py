"""Unit tests for calendar-conversation refresh-before-answer (D150, S55b-1).

The cell refreshes at turn-open within a tier budget; on timeout or
failure it serves the cached Meeting store with a staleness note and does
not fail the turn (D150 Option A).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

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


class _RefreshOk:
    def __init__(self) -> None:
        self.calls = 0

    async def refresh(self, *, tenant_context: Any) -> None:
        self.calls += 1


class _RefreshSlow:
    async def refresh(self, *, tenant_context: Any) -> None:
        await asyncio.sleep(1.0)  # exceeds the test budget


class _RefreshFails:
    async def refresh(self, *, tenant_context: Any) -> None:
        raise CalendarRefreshError("nango unreachable")


def _cell(refresh_port, *, timeout: float = 0.05):
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
        refresh_timeout_seconds=timeout,
        originating_intake_id=uuid4(),
        clock=lambda: _NOW,
    )


def _turn(cell):
    async def _drive():
        state = await cell.open(
            ConversationInvocation(purpose="calendar_query", actor_id="calendar-harness")
        )
        return await cell.turn(state, ConversationInput(text="what's on today?"))

    return asyncio.run(_drive())


def test_refresh_succeeds_then_answers_without_note() -> None:
    refresh = _RefreshOk()
    resp = _turn(_cell(refresh)).payload["calendar_response"]
    assert refresh.calls == 1
    assert resp.staleness_note is None
    assert resp.cited_artefacts  # answered from the (fresh) store


def test_refresh_times_out_falls_back_with_note() -> None:
    resp = _turn(_cell(_RefreshSlow())).payload["calendar_response"]
    assert resp.staleness_note is not None
    assert "timed out" in resp.staleness_note
    assert resp.cited_artefacts  # still answered from the cached store


def test_refresh_fails_falls_back_with_note() -> None:
    resp = _turn(_cell(_RefreshFails())).payload["calendar_response"]
    assert resp.staleness_note is not None
    assert "unavailable" in resp.staleness_note
    assert resp.cited_artefacts  # still answered from the cached store
