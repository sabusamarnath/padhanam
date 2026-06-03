"""Citation-time audit-snapshot evidence tests (D148 option b, D21, S55b-2).

The load-bearing properties: (1) the snapshot in the audit after_state
carries NO plaintext sensitive Meeting content (title/description/location/
attendees) — it is envelope-encrypted per D21, since audit after_state is
plaintext JSONB at rest; (2) the snapshot is decryptable evidence; (3) the
snapshot is frozen at emission and unaffected by later mutation of the
live Meeting row; (4) a cited cell turn emits the meeting_citation event.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from contexts.calendar.domain.meeting import Meeting, MeetingAttendee, MeetingStatus
from contexts.calendar_conversation.application.audit_events import (
    ACTION_MEETING_CITATION_EMIT,
    RESOURCE_TYPE_MEETING_CITATION,
    decrypt_citation_snapshot,
    draft_meeting_citation_event,
    meeting_citation_snapshot,
)
from contexts.calendar_conversation.application.cell import (
    CalendarConversationCell,
)
from contexts.messaging.adapters.threshold_single_pair import (
    SinglePairThresholdResolverAdapter,
)
from shared_kernel import (
    ActorContext,
    ActorReference,
    ConfidenceThresholds,
    ConversationInput,
    ConversationInvocation,
    TenantContext,
)
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles
from tests.unit.contexts.calendar_conversation.test_cell import (
    _FakeMeetingReader,
    _PendingStore,
    _StubConfidence,
    _StubStructuredOutput,
)

_TENANT = "00000000-0000-4000-8000-00000000a001"
_NOW = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)

# Distinctive sensitive content that must never appear in plaintext.
_SECRET_TITLE = "Project Falcon merger sync"
_SECRET_DESC = "acquire Acme Corp for 50M"
_SECRET_LOCATION = "Boardroom 7, 30th floor"
_SECRET_ATTENDEE = "ceo@acme-target.example"


def _sensitive_meeting(*, title: str = _SECRET_TITLE, event_id: str = "evt-secret") -> Meeting:
    return Meeting(
        id=uuid4(),
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        google_event_id=event_id,
        status=MeetingStatus.CONFIRMED,
        title=title,
        description=_SECRET_DESC,
        location=_SECRET_LOCATION,
        attendees=(
            MeetingAttendee(
                email=_SECRET_ATTENDEE, display_name="Target CEO", response_status="accepted"
            ),
        ),
        organizer_email="me@example.com",
        start_at=datetime(2026, 6, 2, 15, 0, tzinfo=timezone.utc),
        end_at=None,
        start_raw="2026-06-02T15:00:00+00:00",
        end_raw=None,
        source_updated_at=None,
        recurring_event_id=None,
        html_link=None,
        content_hash="hash-v1",
        created_at=_NOW,
        updated_at=_NOW,
    )


def test_snapshot_carries_no_plaintext_sensitive_content() -> None:
    snap = meeting_citation_snapshot(_sensitive_meeting(), tenant_id=_TENANT)
    blob = json.dumps(snap)
    for secret in (_SECRET_TITLE, _SECRET_DESC, _SECRET_LOCATION, _SECRET_ATTENDEE):
        assert secret not in blob, f"plaintext leak: {secret!r} in citation snapshot"
    # Non-sensitive metadata IS present (the integrity anchor + identifiers).
    assert snap["content_hash"] == "hash-v1"
    assert snap["google_event_id"] == "evt-secret"
    assert snap["status"] == "confirmed"
    assert "enc_content" in snap


def test_snapshot_decrypts_to_original_content() -> None:
    m = _sensitive_meeting()
    snap = meeting_citation_snapshot(m, tenant_id=_TENANT)
    recovered = decrypt_citation_snapshot(snap, tenant_id=_TENANT)
    assert recovered["title"] == _SECRET_TITLE
    assert recovered["description"] == _SECRET_DESC
    assert recovered["location"] == _SECRET_LOCATION
    assert recovered["attendees"][0]["email"] == _SECRET_ATTENDEE


def test_snapshot_frozen_under_live_row_mutation() -> None:
    # Snapshot the v1 meeting; a later refresh overwrites the live row with
    # a renamed v2 under the same event id. The v1 snapshot is unaffected.
    v1 = _sensitive_meeting(title=_SECRET_TITLE, event_id="evt-x")
    snap_v1 = meeting_citation_snapshot(v1, tenant_id=_TENANT)
    v2 = _sensitive_meeting(title="Renamed innocuous standup", event_id="evt-x")
    snap_v2 = meeting_citation_snapshot(v2, tenant_id=_TENANT)
    # The v1 evidence still decrypts to the original title.
    assert decrypt_citation_snapshot(snap_v1, tenant_id=_TENANT)["title"] == _SECRET_TITLE
    assert decrypt_citation_snapshot(snap_v2, tenant_id=_TENANT)["title"] == "Renamed innocuous standup"


def test_draft_event_shape() -> None:
    m = _sensitive_meeting()
    ctx = TenantContext(tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT)
    event = draft_meeting_citation_event(
        tenant_context=ctx,
        actor=ActorReference(user_id="op"),
        meetings=(m,),
        emitted_at=_NOW.isoformat(),
    )
    assert event.resource_type == RESOURCE_TYPE_MEETING_CITATION
    assert event.action_verb == ACTION_MEETING_CITATION_EMIT
    assert event.resource_id == str(m.id)
    assert event.after_state["cited_count"] == 1
    assert event.this_event_hash  # draft hash present
    # No plaintext leak through the whole after_state either.
    assert _SECRET_TITLE not in json.dumps(event.after_state)


class _RecordingAuditPort:
    def __init__(self) -> None:
        self.events: list[Any] = []

    async def emit(self, event: Any) -> Any:
        self.events.append(event)
        return event


def _actor() -> ActorContext:
    tenant = TenantContext(tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT)
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=tenant,
        actor_id="citation-harness",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def test_cited_cell_turn_emits_meeting_citation_event() -> None:
    audit = _RecordingAuditPort()
    cell = CalendarConversationCell(
        structured_output_port=_StubStructuredOutput(
            {"intent_class": "find_by_date_range", "range_keyword": "today", "confidence": 0.95}
        ),
        meeting_reader=_FakeMeetingReader((_sensitive_meeting(),)),
        actor=_actor(),
        confidence_calculator=_StubConfidence(),
        threshold_resolver=SinglePairThresholdResolverAdapter(
            thresholds=ConfidenceThresholds(high=0.8, medium=0.5),
        ),
        pending_clarification_reader=_PendingStore(),
        pending_clarification_repository=_PendingStore(),
        audit_port=audit,
        originating_intake_id=uuid4(),
        clock=lambda: _NOW,
    )

    async def _drive():
        st = await cell.open(
            ConversationInvocation(purpose="calendar_query", actor_id="citation-harness")
        )
        return await cell.turn(st, ConversationInput(text="what's on today?"))

    state = asyncio.run(_drive())
    citation_events = [
        e for e in audit.events if e.resource_type == RESOURCE_TYPE_MEETING_CITATION
    ]
    assert len(citation_events) == 1
    ev = citation_events[0]
    assert ev.after_state["cited_count"] == 1
    # Evidence is recoverable; no plaintext in the event.
    assert _SECRET_TITLE not in json.dumps(ev.after_state)
    snap = ev.after_state["cited_meetings"][0]
    assert decrypt_citation_snapshot(snap, tenant_id=_TENANT)["title"] == _SECRET_TITLE
    # The response itself still rendered with the citation.
    assert state.payload["calendar_response"].cited_artefacts
