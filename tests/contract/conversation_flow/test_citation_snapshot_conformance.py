"""Citation-snapshot evidence conformance (D148 option b, D21, P15, S55b-2).

Calendar Meetings are the platform's first mutable cited source, so the
citation evidence must be decoupled from the live row: a snapshot frozen
at citation time must survive the live row's mutation on a later refresh.
This contract scenario drives the calendar-conversation cell through a
cited turn, captures the emitted ``meeting_citation`` audit event, then
simulates a refresh that overwrites the live row under the same event id —
and asserts the first event's snapshot still decrypts to the original
content (and carries no plaintext). The unit suite covers the same
properties at finer grain; this binds them at the contract altitude
alongside the CitedResponse and resolution-ambiguity scenarios.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from contexts.calendar.domain.meeting import Meeting, MeetingAttendee, MeetingStatus
from contexts.calendar_conversation.application.audit_events import (
    RESOURCE_TYPE_MEETING_CITATION,
    decrypt_citation_snapshot,
)
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
    TenantContext,
)
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles

_TENANT = "00000000-0000-4000-8000-00000000a004"
_NOW = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)


class _StubStructuredOutput:
    async def generate_structured(self, request: Any) -> Any:
        from shared_kernel import StructuredOutputResponse

        value = {
            "intent_class": "find_by_date_range",
            "range_keyword": "today",
            "confidence": 0.95,
        }
        return StructuredOutputResponse(
            value=value, confidence=0.95, provider_metadata={}
        )


class _StubConfidence:
    def compute(self, *, request: Any, response: Any) -> float:
        return 0.95


class _MutableReader:
    """A reader whose backing meeting can be swapped to simulate a refresh."""

    def __init__(self, meeting: Meeting) -> None:
        self.meeting = meeting

    async def list_meetings(self, *, tenant_context: Any, include_cancelled: bool = False):
        return (self.meeting,)

    async def get_by_event_id(self, *, tenant_context: Any, google_event_id: str):
        return self.meeting if self.meeting.google_event_id == google_event_id else None


class _NoPending:
    async def get_active(self, *, tenant_id: Any, user_id: str) -> Any:
        return None

    async def save(self, **k: Any) -> None:
        return None

    async def update_status(self, **k: Any) -> None:
        return None

    async def get_by_id(self, **k: Any) -> Any:
        return None

    async def get_active_for_user(self, **k: Any) -> Any:
        return None


class _RecordingAudit:
    def __init__(self) -> None:
        self.events: list[Any] = []

    async def emit(self, event: Any) -> Any:
        self.events.append(event)
        return event


def _meeting(title: str) -> Meeting:
    return Meeting(
        id=uuid4(),
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        google_event_id="evt-mutating",
        status=MeetingStatus.CONFIRMED,
        title=title,
        description="confidential agenda",
        location="Boardroom",
        attendees=(MeetingAttendee(email="a@x.com", display_name="A", response_status="accepted"),),
        organizer_email="me@example.com",
        start_at=datetime(2026, 6, 2, 15, 0, tzinfo=timezone.utc),
        end_at=None,
        start_raw="2026-06-02T15:00:00+00:00",
        end_raw=None,
        source_updated_at=None,
        recurring_event_id=None,
        html_link=None,
        content_hash="h",
        created_at=_NOW,
        updated_at=_NOW,
    )


def _actor() -> ActorContext:
    tenant = TenantContext(tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT)
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=tenant,
        actor_id="citation-conformance",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def test_citation_snapshot_survives_live_row_mutation() -> None:
    original_title = "Project Falcon merger"
    reader = _MutableReader(_meeting(original_title))
    audit = _RecordingAudit()
    cell = CalendarConversationCell(
        structured_output_port=_StubStructuredOutput(),
        meeting_reader=reader,
        actor=_actor(),
        confidence_calculator=_StubConfidence(),
        threshold_resolver=SinglePairThresholdResolverAdapter(
            thresholds=ConfidenceThresholds(high=0.8, medium=0.5),
        ),
        pending_clarification_reader=_NoPending(),
        pending_clarification_repository=_NoPending(),
        audit_port=audit,
        originating_intake_id=uuid4(),
        clock=lambda: _NOW,
    )

    async def _turn():
        st = await cell.open(
            ConversationInvocation(purpose="calendar_query", actor_id="citation-conformance")
        )
        return await cell.turn(st, ConversationInput(text="what's on today?"))

    asyncio.run(_turn())
    citation_events = [
        e for e in audit.events if e.resource_type == RESOURCE_TYPE_MEETING_CITATION
    ]
    assert len(citation_events) == 1
    frozen_event = citation_events[0]
    frozen_snapshot = frozen_event.after_state["cited_meetings"][0]

    # No plaintext sensitive content reached the audit after_state.
    assert original_title not in json.dumps(frozen_event.after_state)
    assert "confidential agenda" not in json.dumps(frozen_event.after_state)

    # Now a refresh overwrites the live row under the same event id.
    reader.meeting = _meeting("Renamed weekly standup")
    asyncio.run(_turn())  # a second cited turn, snapshotting the new title

    # The FIRST event's evidence still decrypts to the original content —
    # the snapshot is frozen, decoupled from the mutated live row (D148 b).
    recovered = decrypt_citation_snapshot(frozen_snapshot, tenant_id=_TENANT)
    assert recovered["title"] == original_title

    # And the second event reflects the mutation (the live row did change).
    second_event = [
        e for e in audit.events if e.resource_type == RESOURCE_TYPE_MEETING_CITATION
    ][1]
    second_snapshot = second_event.after_state["cited_meetings"][0]
    assert decrypt_citation_snapshot(second_snapshot, tenant_id=_TENANT)["title"] == "Renamed weekly standup"
