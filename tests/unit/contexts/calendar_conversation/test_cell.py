"""Unit tests for the calendar-conversation cell (D138, D139, D148, S55b-1).

Offline stubs (no LLM, no DB) exercise the four query intents, the
three-case confidence discipline, and D139 resolution-ambiguity routing
through PendingClarification including positional selection.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest

from contexts.calendar_conversation.application.cell import (
    CalendarConversationCell,
)
from contexts.messaging.adapters.threshold_single_pair import (
    SinglePairThresholdResolverAdapter,
)
from shared_kernel import (
    ActorContext,
    ConfidenceThresholds,
    ConversationInput,
    ConversationInvocation,
    StructuredOutputParseFailure,
    StructuredOutputResponse,
    TenantContext,
)
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles
from tests.unit.contexts.calendar_conversation.conftest import make_meeting

_NOW = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
_TENANT = "00000000-0000-4000-8000-00000000a001"


class _StubStructuredOutput:
    def __init__(self, value: dict[str, Any], *, raise_parse: bool = False) -> None:
        self._value = value
        self._raise = raise_parse

    async def generate_structured(self, request: Any) -> Any:
        if self._raise:
            raise StructuredOutputParseFailure("bad")
        return StructuredOutputResponse(
            value=self._value,
            confidence=float(self._value.get("confidence", 0.0)),
            provider_metadata={},
        )


class _StubConfidence:
    def compute(self, *, request: Any, response: Any) -> float:
        return float(getattr(response, "confidence", 0.0) or 0.0)


class _FakeMeetingReader:
    def __init__(self, meetings: tuple) -> None:
        self._meetings = meetings

    async def list_meetings(self, *, tenant_context: Any, include_cancelled: bool = False):
        return self._meetings

    async def get_by_event_id(self, *, tenant_context: Any, google_event_id: str):
        for m in self._meetings:
            if m.google_event_id == google_event_id:
                return m
        return None


class _PendingStore:
    """Shared in-memory PendingClarification repo + reader."""

    def __init__(self) -> None:
        self.saved: list[Any] = []
        self._active: Any = None

    # repository side
    async def save(self, *, tenant_context: Any, pending: Any) -> None:
        self.saved.append(pending)
        self._active = pending

    async def update_status(self, *, tenant_context: Any, pending: Any) -> None:
        self._active = None  # terminal status clears the active pending

    async def get_by_id(self, *, tenant_context: Any, pending_id: Any) -> Any:
        return None

    async def get_active_for_user(self, *, tenant_context: Any, user_id: str) -> Any:
        return self._active

    # reader side
    async def get_active(self, *, tenant_id: Any, user_id: str) -> Any:
        return self._active


class _StubAuditPort:
    async def emit(self, event: Any) -> Any:
        return event


def _actor() -> ActorContext:
    tenant = TenantContext(
        tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
    )
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=tenant,
        actor_id="calendar-harness",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def _cell(value: dict, *, meetings: tuple = (), raise_parse: bool = False, store: _PendingStore | None = None):
    store = store or _PendingStore()
    cell = CalendarConversationCell(
        structured_output_port=_StubStructuredOutput(value, raise_parse=raise_parse),
        meeting_reader=_FakeMeetingReader(meetings),
        actor=_actor(),
        confidence_calculator=_StubConfidence(),
        threshold_resolver=SinglePairThresholdResolverAdapter(
            thresholds=ConfidenceThresholds(high=0.8, medium=0.5),
        ),
        pending_clarification_reader=store,
        pending_clarification_repository=store,
        audit_port=_StubAuditPort(),
        originating_intake_id=uuid4(),
        clock=lambda: _NOW,
    )
    return cell, store


def _turn(cell, text: str):
    async def _drive():
        state = await cell.open(
            ConversationInvocation(purpose="calendar_query", actor_id="calendar-harness")
        )
        return await cell.turn(state, ConversationInput(text=text))

    return asyncio.run(_drive())


def test_find_by_date_range_cites_meetings() -> None:
    m = make_meeting(title="Board sync", start_at=datetime(2026, 6, 2, 15, 0, tzinfo=timezone.utc))
    cell, _ = _cell(
        {"intent_class": "find_by_date_range", "range_keyword": "today", "confidence": 0.95},
        meetings=(m,),
    )
    state = _turn(cell, "what's on today?")
    resp = state.payload["calendar_response"]
    assert state.payload["confidence_band"] == "high"
    assert resp.cited_artefacts and resp.cited_artefacts[0].artefact_type == "meeting"
    assert "Board sync" in resp.text


def test_find_by_attendee() -> None:
    m = make_meeting(title="1:1", start_at=_NOW, attendees=("ada@x.com",))
    cell, _ = _cell(
        {"intent_class": "find_by_attendee", "attendee": "ada", "confidence": 0.95},
        meetings=(m,),
    )
    resp = _turn(cell, "meetings with ada").payload["calendar_response"]
    assert len(resp.cited_artefacts) == 1


def test_find_next_meeting() -> None:
    soon = make_meeting(title="soon", start_at=datetime(2026, 6, 2, 15, 0, tzinfo=timezone.utc))
    cell, _ = _cell(
        {"intent_class": "find_next_meeting", "confidence": 0.95}, meetings=(soon,)
    )
    resp = _turn(cell, "what's next?").payload["calendar_response"]
    assert "soon" in resp.text and len(resp.cited_artefacts) == 1


def test_find_by_title_single_match() -> None:
    m = make_meeting(title="Quarterly business review", start_at=_NOW)
    cell, _ = _cell(
        {"intent_class": "find_by_title", "title_reference": "quarterly business review", "confidence": 0.95},
        meetings=(m,),
    )
    resp = _turn(cell, "the QBR").payload["calendar_response"]
    assert len(resp.cited_artefacts) == 1


def test_medium_confidence_persists_pending_and_does_not_query() -> None:
    m = make_meeting(title="x", start_at=_NOW)
    cell, store = _cell(
        {"intent_class": "find_by_date_range", "range_keyword": "today", "confidence": 0.6},
        meetings=(m,),
    )
    state = _turn(cell, "today?")
    assert state.payload["confidence_band"] == "medium"
    assert len(store.saved) == 1
    assert not state.payload["calendar_response"].has_citations


def test_unclear_intent_clarifies() -> None:
    cell, _ = _cell(
        {"intent_class": "unclear_calendar", "clarification": "What would you like to know?", "confidence": 0.9}
    )
    state = _turn(cell, "blah")
    assert state.payload["confidence_band"] == "low"
    assert "What would you like to know?" in state.payload["response_text"]


def test_parse_failure_clarifies() -> None:
    cell, _ = _cell({}, raise_parse=True)
    state = _turn(cell, "???")
    assert state.payload["confidence_band"] == "parse_failure"


def test_resolution_ambiguity_persists_pending_with_candidates() -> None:
    a = make_meeting(title="Board sync", start_at=_NOW)
    b = make_meeting(title="Board sync", start_at=_NOW)
    cell, store = _cell(
        {"intent_class": "find_by_title", "title_reference": "board sync", "confidence": 0.95},
        meetings=(a, b),
    )
    state = _turn(cell, "the board sync")
    assert state.payload["confidence_band"] == "resolution_ambiguous"
    assert len(store.saved) == 1
    candidates = store.saved[0].proposed_intent.get("resolution_candidates")
    assert candidates is not None and len(candidates) == 2


def test_positional_selection_resolves_and_composes() -> None:
    a = make_meeting(title="Board sync", start_at=_NOW, event_id="evt-a")
    b = make_meeting(title="Board sync", start_at=_NOW, event_id="evt-b")
    cell, store = _cell(
        {"intent_class": "find_by_title", "title_reference": "board sync", "confidence": 0.95},
        meetings=(a, b),
    )

    async def _drive():
        state = await cell.open(
            ConversationInvocation(purpose="calendar_query", actor_id="calendar-harness")
        )
        # Turn 1: ambiguous -> pending persisted.
        state = await cell.turn(state, ConversationInput(text="the board sync"))
        # Turn 2: positional selection "1".
        return await cell.turn(state, ConversationInput(text="1"))

    final = asyncio.run(_drive())
    resp = final.payload["calendar_response"]
    assert final.payload["confidence_band"] == "resolution_selected"
    assert len(resp.cited_artefacts) == 1
