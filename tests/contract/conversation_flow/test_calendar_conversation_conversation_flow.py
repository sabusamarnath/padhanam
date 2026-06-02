"""Register the calendar-conversation cell with the ConversationFlow harness (D148, D150, S55b-1).

P15's calendar-conversation ConversationFlow implementer registers via
this module. The parametrised lifecycle scenarios in
``test_conversation_flow_contract.py`` plus the CitedResponse-conformance
and resolution-ambiguity-conformance scenarios run against it.

``make_instance`` builds the cell with offline stubs: the structured-
output stub returns an UnclearCalendarIntent extraction so a harness
``turn`` runs without an LLM call. No refresh port is wired in the
harness build (refresh is exercised by the cell's own unit tests); the
harness path serves the cached store.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from contexts.calendar.domain.meeting import (
    Meeting,
    MeetingAttendee,
    MeetingStatus,
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
    ConversationClosure,
    ConversationInput,
    ConversationInvocation,
    StructuredOutputResponse,
    TenantContext,
)
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles

from tests.contract.conversation_flow.conftest import (
    ConversationFlowImplementerFixture,
    register_conversation_flow_implementer,
)

_TENANT = "00000000-0000-4000-8000-00000000a004"


class _StubStructuredOutput:
    def __init__(self, value: dict[str, Any] | None = None) -> None:
        self._value = value or {
            "intent_class": "unclear_calendar",
            "clarification": "Could you specify the calendar query?",
            "confidence": 0.0,
        }

    async def generate_structured(
        self, request: Any
    ) -> StructuredOutputResponse[dict[str, Any]]:
        return StructuredOutputResponse(
            value=self._value,
            confidence=float(self._value.get("confidence", 0.0)),
            provider_metadata={},
        )


class _StubMeetingReader:
    def __init__(self, meetings: tuple[Meeting, ...] = ()) -> None:
        self._meetings = meetings

    async def list_meetings(
        self, *, tenant_context: Any, include_cancelled: bool = False
    ) -> tuple[Meeting, ...]:
        return self._meetings

    async def get_by_event_id(
        self, *, tenant_context: Any, google_event_id: str
    ) -> Meeting | None:
        for m in self._meetings:
            if m.google_event_id == google_event_id:
                return m
        return None


class _StubConfidenceCalculator:
    def compute(self, *, request: Any, response: Any) -> float:
        return float(getattr(response, "confidence", 0.0) or 0.0)


class _StubPendingRepo:
    def __init__(self) -> None:
        self.saved: list[Any] = []

    async def save(self, *, tenant_context: Any, pending: Any) -> None:
        self.saved.append(pending)

    async def update_status(self, *, tenant_context: Any, pending: Any) -> None:
        return None

    async def get_by_id(self, *, tenant_context: Any, pending_id: Any) -> Any:
        return None

    async def get_active_for_user(self, *, tenant_context: Any, user_id: str) -> Any:
        return None


class _StubPendingReader:
    async def get_active(self, *, tenant_id: Any, user_id: str) -> Any:
        return None


class _StubAuditPort:
    async def emit(self, event: Any) -> Any:
        return event


def _harness_actor() -> ActorContext:
    tenant = TenantContext(
        tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
    )
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=tenant,
        actor_id="calendar-conversation-harness",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def _meeting(title: str, *, event_id: str) -> Meeting:
    now = datetime(2026, 6, 2, 9, 0, tzinfo=timezone.utc)
    return Meeting(
        id=uuid4(),
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        google_event_id=event_id,
        status=MeetingStatus.CONFIRMED,
        title=title,
        description=None,
        location=None,
        attendees=(MeetingAttendee(email="a@x.com", display_name="Ada", response_status="accepted"),),
        organizer_email=None,
        start_at=datetime(2026, 6, 2, 15, 0, tzinfo=timezone.utc),
        end_at=None,
        start_raw="2026-06-02T15:00:00+00:00",
        end_raw=None,
        source_updated_at=None,
        recurring_event_id=None,
        html_link=None,
        content_hash="h",
        created_at=now,
        updated_at=now,
    )


def _make_calendar_conversation_cell(
    *,
    extraction: dict[str, Any] | None = None,
    meetings: tuple[Meeting, ...] = (),
    pending_repo: _StubPendingRepo | None = None,
) -> CalendarConversationCell:
    return CalendarConversationCell(
        structured_output_port=_StubStructuredOutput(extraction),
        meeting_reader=_StubMeetingReader(meetings),
        actor=_harness_actor(),
        confidence_calculator=_StubConfidenceCalculator(),
        threshold_resolver=SinglePairThresholdResolverAdapter(
            thresholds=ConfidenceThresholds(high=0.8, medium=0.5),
        ),
        pending_clarification_reader=_StubPendingReader(),
        pending_clarification_repository=pending_repo or _StubPendingRepo(),
        audit_port=_StubAuditPort(),
        originating_intake_id=uuid4(),
        clock=lambda: datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc),
    )


register_conversation_flow_implementer(
    ConversationFlowImplementerFixture(
        name="calendar_conversation_cell",
        implementer_cls=CalendarConversationCell,
        make_instance=_make_calendar_conversation_cell,
        sample_invocation=ConversationInvocation(
            purpose="calendar_query",
            actor_id="calendar-conversation-harness",
        ),
        sample_input=ConversationInput(text="what's on my calendar today?"),
        sample_closure=ConversationClosure(reason="harness closed"),
    )
)


def build_calendar_conversation_with_ambiguous_resolution() -> tuple[
    CalendarConversationCell, _StubPendingRepo
]:
    """Build the cell in a title-ambiguous condition for the D139 scenario."""
    repo = _StubPendingRepo()
    cell = _make_calendar_conversation_cell(
        extraction={
            "intent_class": "find_by_title",
            "title_reference": "Q3 portfolio review",
            "confidence": 0.95,
        },
        meetings=(
            _meeting("Q3 portfolio review", event_id="evt-a"),
            _meeting("Q3 portfolio review", event_id="evt-b"),
        ),
        pending_repo=repo,
    )
    return cell, repo
