"""Unit tests for the AuditConversationCell ConversationFlow implementer (S51)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from contexts.audit.domain.audit_event_record import AuditEventRecord
from contexts.audit.domain.chain_integrity import ChainIntegrityVerification
from contexts.audit.domain.events import AuditEvent
from contexts.audit.domain.query_filters import (
    AuditEventListCursor,
    AuditEventListFilters,
    AuditEventListPage,
)

from contexts.audit_conversation.application.cell import AuditConversationCell
from contexts.audit_conversation.application.ports.portfolio_case_lookup import (
    AuditCaseSummary,
)
from contexts.audit_conversation.application.response import (
    AuditConversationResponse,
)
from contexts.audit_conversation.domain.intent import AuditIntentType

from contexts.messaging.api import PendingClarification
from contexts.messaging.domain.pending_clarification import (
    PendingClarificationStatus,
)

from shared_kernel import (
    ActorContext,
    ConversationClosure,
    ConversationFlow,
    ConversationInput,
    ConversationInvocation,
    LatencyTier,
    StructuredOutputParseFailure,
    StructuredOutputRequest,
    StructuredOutputResponse,
    TenantContext,
)
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles
from shared_kernel.confidence_thresholds import ConfidenceThresholds


# ----------------------------------------------------------------- helpers

_HARNESS_TENANT_ID = "11111111-1111-1111-1111-111111111111"
_HARNESS_USER_ID = "operator"


def _actor() -> ActorContext:
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_HARNESS_TENANT_ID,
            jurisdiction="US",
            cost_attribution_id="harness",
        ),
        actor_id=_HARNESS_USER_ID,
        role_list=frozenset({ROLE_OPERATOR}),
        authorisation_set=authorisations_for_roles(frozenset({ROLE_OPERATOR})),
    )


class _StubStructuredOutput:
    def __init__(self, value: dict[str, Any]) -> None:
        self.value = value

    async def generate_structured(
        self, request: StructuredOutputRequest
    ) -> StructuredOutputResponse:
        return StructuredOutputResponse(
            value=self.value,
            confidence=float(self.value.get("confidence", 0.9)),
            provider_metadata={},
        )


class _ParseFailingStructuredOutput:
    async def generate_structured(
        self, request: StructuredOutputRequest
    ) -> StructuredOutputResponse:
        raise StructuredOutputParseFailure("synthetic")


class _StubAuditReader:
    def __init__(self, events: tuple[AuditEventRecord, ...]) -> None:
        self.events = events
        self.calls: list[AuditEventListFilters] = []

    async def get_audit_event(
        self, *, destination, event_id, tenant_context
    ) -> AuditEventRecord | None:
        for event in self.events:
            if event.id == event_id:
                return event
        return None

    async def list_audit_events_with_filters(
        self,
        *,
        destination: AuditDestination,
        filters: AuditEventListFilters,
        cursor: AuditEventListCursor | None,
        page_size: int,
        tenant_context: TenantContext | None,
    ) -> AuditEventListPage:
        self.calls.append(filters)
        return AuditEventListPage(
            events=self.events,
            next_cursor=None,
            chain_integrity=ChainIntegrityVerification(status="verified"),
        )

    async def verify_chain_segment(
        self, *, destination, events
    ) -> ChainIntegrityVerification:
        return ChainIntegrityVerification(status="verified")


class _StubCaseLookup:
    def __init__(self, cases: tuple[AuditCaseSummary, ...]) -> None:
        self.cases = cases

    async def find_cases(
        self, *, actor: ActorContext
    ) -> tuple[AuditCaseSummary, ...]:
        return self.cases


class _StubConfidenceCalculator:
    def __init__(self, value: float = 0.9) -> None:
        self.value = value

    def compute(self, *, request, response) -> float:
        # Defer to response's self-reported confidence if present.
        return getattr(response, "confidence", self.value)


class _StaticThresholds:
    def resolve(self, *, operation_class: str) -> ConfidenceThresholds:
        return ConfidenceThresholds(high=0.8, medium=0.5)


class _StubPendingReader:
    def __init__(self, active: PendingClarification | None = None) -> None:
        self.active = active

    async def get_active(
        self, *, tenant_id: str, user_id: str
    ) -> PendingClarification | None:
        return self.active


class _StubPendingRepository:
    def __init__(self) -> None:
        self.saved: list[PendingClarification] = []
        self.status_updates: list[PendingClarification] = []

    async def save(self, *, tenant_context, pending) -> None:
        self.saved.append(pending)

    async def update_status(self, *, tenant_context, pending) -> None:
        self.status_updates.append(pending)

    async def get_by_id(self, *, tenant_context, pending_id):
        for p in self.saved:
            if p.id == pending_id:
                return p
        return None

    async def get_active_for_user(self, *, tenant_context, user_id):
        for p in self.saved:
            if (
                p.user_id == user_id
                and p.status == PendingClarificationStatus.PENDING
            ):
                return p
        return None


class _StubAuditPort:
    def __init__(self) -> None:
        self.emitted: list[AuditEvent] = []

    async def emit(self, event: AuditEvent) -> None:
        self.emitted.append(event)


def _audit_event(
    *,
    event_id: UUID | None = None,
    action_verb: str = "portfolio.case.create",
    resource_type: str = "case",
    resource_id: str | None = None,
    actor: str = "operator",
    timestamp: datetime | None = None,
) -> AuditEventRecord:
    return AuditEventRecord(
        id=event_id or uuid4(),
        tenant_id=_HARNESS_TENANT_ID,
        actor=actor,
        jurisdiction="US",
        timestamp=timestamp or datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc),
        action_verb=action_verb,
        resource_type=resource_type,
        resource_id=resource_id or str(uuid4()),
        before_state={},
        after_state={},
        correlation_id="",
        previous_event_hash="0" * 64,
        this_event_hash="1" * 64,
    )


def _cell(
    *,
    extraction: dict[str, Any] | None = None,
    parse_fails: bool = False,
    events: tuple[AuditEventRecord, ...] = (),
    cases: tuple[AuditCaseSummary, ...] = (),
    active_pending: PendingClarification | None = None,
) -> AuditConversationCell:
    pending_repo = _StubPendingRepository()
    structured: Any
    if parse_fails:
        structured = _ParseFailingStructuredOutput()
    else:
        structured = _StubStructuredOutput(extraction or {"intent_class": "unclear_audit", "clarification": "?", "confidence": 0.1})
    return AuditConversationCell(
        structured_output_port=structured,
        audit_event_reader=_StubAuditReader(events),
        portfolio_case_lookup=_StubCaseLookup(cases),
        actor=_actor(),
        confidence_calculator=_StubConfidenceCalculator(),
        threshold_resolver=_StaticThresholds(),
        pending_clarification_reader=_StubPendingReader(active_pending),
        pending_clarification_repository=pending_repo,
        audit_port=_StubAuditPort(),
        originating_intake_id=uuid4(),
        clock=lambda: datetime(2026, 5, 26, 14, 30, tzinfo=timezone.utc),
    )


async def _open_and_turn(
    cell: AuditConversationCell, text: str
):
    state = await cell.open(
        ConversationInvocation(purpose="audit_query", actor_id=_HARNESS_USER_ID)
    )
    return await cell.turn(state, ConversationInput(text=text))


def _run(coro):
    return asyncio.run(coro)


# ----------------------------------------------------------------- tests


def test_cell_satisfies_conversation_flow_protocol() -> None:
    cell = _cell()
    assert isinstance(cell, ConversationFlow)


def test_find_by_date_range_high_confidence_executes_query() -> None:
    event = _audit_event()
    cell = _cell(
        extraction={
            "intent_class": "find_by_date_range",
            "range_keyword": "today",
            "confidence": 0.95,
        },
        events=(event,),
    )

    state = _run(_open_and_turn(cell, "show audit events for today"))

    response: AuditConversationResponse = state.payload["audit_response"]
    assert isinstance(response, AuditConversationResponse)
    assert response.cited_audit_events == (event.id,)
    assert state.payload["intent_class"] == AuditIntentType.FIND_BY_DATE_RANGE.value
    assert state.payload["confidence_band"] == "high"


def test_find_by_actor_populates_audit_event_citations() -> None:
    e1 = _audit_event(actor="alice")
    e2 = _audit_event(actor="alice", resource_type="data_point")
    cell = _cell(
        extraction={
            "intent_class": "find_by_actor",
            "actor": "alice",
            "confidence": 0.95,
        },
        events=(e1, e2),
    )

    state = _run(_open_and_turn(cell, "what has alice done"))

    response: AuditConversationResponse = state.payload["audit_response"]
    assert len(response.cited_audit_events) == 2
    # Heterogeneous cited_artefacts: one case, one data_point
    types = {a.artefact_type for a in response.cited_artefacts}
    assert types == {"case", "data_point"}


def test_find_by_event_type_maps_to_action_verbs_filter() -> None:
    event = _audit_event(action_verb="portfolio.case.create")
    reader_calls: list[AuditEventListFilters] = []
    cell = _cell(
        extraction={
            "intent_class": "find_by_event_type",
            "event_type": "portfolio.case.create",
            "confidence": 0.95,
        },
        events=(event,),
    )
    _run(_open_and_turn(cell, "show case creates"))

    # The stub reader records every filter call.
    captured = cell._audit_reader.calls  # type: ignore[attr-defined]
    assert len(captured) == 1
    assert captured[0].action_verbs == ("portfolio.case.create",)


def test_empty_query_result_returns_no_citations() -> None:
    cell = _cell(
        extraction={
            "intent_class": "find_by_actor",
            "actor": "bob",
            "confidence": 0.95,
        },
        events=(),
    )
    state = _run(_open_and_turn(cell, "what has bob done"))
    response: AuditConversationResponse = state.payload["audit_response"]
    assert not response.has_citations
    assert "No audit events matched" in response.text


def test_parse_failure_routes_to_unclear_clarification() -> None:
    cell = _cell(parse_fails=True)
    state = _run(_open_and_turn(cell, "garbled"))
    assert state.payload["confidence_band"] == "parse_failure"
    response: AuditConversationResponse = state.payload["audit_response"]
    assert not response.has_citations


def test_low_confidence_routes_to_unclear_clarification() -> None:
    cell = _cell(
        extraction={
            "intent_class": "unclear_audit",
            "clarification": "Could you clarify?",
            "confidence": 0.1,
        }
    )
    state = _run(_open_and_turn(cell, "hmm"))
    assert state.payload["confidence_band"] == "low"


def test_find_by_case_resolution_ambiguous_routes_to_pending() -> None:
    # Two cases share the same significant tokens → ambiguous.
    case_a = AuditCaseSummary(case_id=uuid4(), title="Q3 portfolio review")
    case_b = AuditCaseSummary(case_id=uuid4(), title="Q3 portfolio review")
    cell = _cell(
        extraction={
            "intent_class": "find_by_case",
            "case_reference": "Q3 portfolio review",
            "confidence": 0.95,
        },
        events=(_audit_event(),),
        cases=(case_a, case_b),
    )

    state = _run(_open_and_turn(cell, "audit for the Q3 portfolio review"))

    assert state.payload["confidence_band"] == "resolution_ambiguous"
    response: AuditConversationResponse = state.payload["audit_response"]
    # Each candidate cited via cited_artefacts per D139.
    assert len(response.cited_artefacts) == 2
    assert {a.artefact_type for a in response.cited_artefacts} == {"case"}
    # A PendingClarification persisted via the repository.
    repo = cell._pending_repo  # type: ignore[attr-defined]
    assert len(repo.saved) == 1
    saved = repo.saved[0]
    assert "resolution_candidates" in saved.proposed_intent
    assert len(saved.proposed_intent["resolution_candidates"]) == 2


def test_find_by_case_unique_match_proceeds_directly() -> None:
    case = AuditCaseSummary(case_id=uuid4(), title="Q3 portfolio review")
    event = _audit_event(resource_type="case", resource_id=str(case.case_id))
    cell = _cell(
        extraction={
            "intent_class": "find_by_case",
            "case_reference": "Q3 portfolio review",
            "confidence": 0.95,
        },
        events=(event,),
        cases=(case,),
    )

    state = _run(_open_and_turn(cell, "audit for Q3 portfolio review"))
    assert state.payload["confidence_band"] == "high"
    response: AuditConversationResponse = state.payload["audit_response"]
    assert event.id in response.cited_audit_events


def test_find_by_case_no_match_returns_clarification() -> None:
    cell = _cell(
        extraction={
            "intent_class": "find_by_case",
            "case_reference": "Nonexistent",
            "confidence": 0.95,
        },
        cases=(),
    )
    state = _run(_open_and_turn(cell, "audit for Nonexistent"))
    assert state.payload["confidence_band"] == "resolution_no_match"


def test_close_returns_outcome() -> None:
    cell = _cell()
    state = _run(cell.open(
        ConversationInvocation(purpose="audit_query", actor_id=_HARNESS_USER_ID)
    ))
    outcome = _run(cell.close(state, ConversationClosure(reason="done")))
    assert outcome.resolution == "done"
    assert outcome.conversation_id == state.conversation_id
