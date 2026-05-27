"""Unit tests for the MirrorConversationCell (P14, S52)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from contexts.audit.domain.events import AuditEvent

from contexts.messaging.adapters.threshold_single_pair import (
    SinglePairThresholdResolverAdapter,
)
from contexts.messaging.domain.pending_clarification import (
    PendingClarification,
    PendingClarificationStatus,
)

from contexts.mirror_conversation.application.cell import (
    MirrorConversationCell,
)
from contexts.mirror_conversation.application.ports.mirror_portfolio_reader import (  # noqa: E501
    MirrorCaseDetail,
    MirrorCaseSummary,
    MirrorDataPoint,
    MirrorDataPointSummary,
)
from contexts.mirror_conversation.application.response import (
    MirrorConversationResponse,
)
from shared_kernel import (
    ActorContext,
    ConfidenceThresholds,
    ConversationInput,
    ConversationInvocation,
    StructuredOutputResponse,
    TenantContext,
)
from shared_kernel.authorisation import (
    ROLE_OPERATOR,
    authorisations_for_roles,
)
from shared_kernel.conversation_flow import ArtefactCitation, CitedResponse


_TENANT_ID = "00000000-0000-4000-8000-00000000a002"


def _actor() -> ActorContext:
    tc = TenantContext(
        tenant_id=_TENANT_ID,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_ID,
    )
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=tc,
        actor_id="mirror-test-actor",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def _summary(title: str = "Q3 portfolio review") -> MirrorCaseSummary:
    now = datetime(2026, 5, 27, 14, 30, tzinfo=timezone.utc)
    return MirrorCaseSummary(
        case_id=uuid4(),
        title=title,
        case_status="OPEN",
        created_at=now,
        last_activity_at=now,
        data_point_count=2,
    )


def _data_point_summary(
    case_id: UUID, label: str = "revenue", dp_type: str = "GOAL"
) -> MirrorDataPointSummary:
    return MirrorDataPointSummary(
        data_point_id=uuid4(),
        case_id=case_id,
        data_point_type=dp_type,
        label=label,
        created_at=datetime(2026, 5, 27, 14, 30, tzinfo=timezone.utc),
    )


def _detail(*labels: str) -> MirrorCaseDetail:
    case_summary = _summary()
    dps = tuple(
        _data_point_summary(case_summary.case_id, label=label)
        for label in labels
    )
    return MirrorCaseDetail(
        case=case_summary,
        data_points=dps,
    )


class _StubMirrorReader:
    def __init__(
        self,
        *,
        cases: tuple[MirrorCaseSummary, ...] = (),
        detail: MirrorCaseDetail | None = None,
        data_point: MirrorDataPoint | None = None,
    ) -> None:
        self.cases = cases
        self.detail = detail
        self.data_point = data_point

    async def list_cases(self, *, actor: ActorContext, limit: int = 50):
        return self.cases

    async def get_case_detail(
        self, *, actor: ActorContext, case_id: UUID
    ):
        if self.detail is None:
            return None
        if self.detail.case.case_id != case_id:
            return None
        return self.detail

    async def get_data_point(
        self, *, actor: ActorContext, data_point_id: UUID
    ):
        return self.data_point

    async def find_cases(self, *, actor: ActorContext):
        return self.cases


class _StubStructuredOutput:
    def __init__(
        self,
        value: dict[str, Any],
        *,
        confidence: float = 0.95,
    ) -> None:
        self._value = value
        self._confidence = confidence

    async def generate_structured(self, request: Any):
        return StructuredOutputResponse(
            value=self._value,
            confidence=self._confidence,
            provider_metadata={},
        )


class _StubConfidenceCalc:
    def compute(self, *, request: Any, response: Any) -> float:
        return float(getattr(response, "confidence", 0.0) or 0.0)


class _StubPendingReader:
    def __init__(self, active: PendingClarification | None = None) -> None:
        self.active = active

    async def get_active(self, *, tenant_id: UUID, user_id: str):
        return self.active


class _StubPendingRepo:
    def __init__(self) -> None:
        self.saved: list[PendingClarification] = []

    async def save(self, *, tenant_context, pending) -> None:
        self.saved.append(pending)

    async def update_status(self, *, tenant_context, pending) -> None:
        return None

    async def get_by_id(self, *, tenant_context, pending_id):
        return None

    async def get_active_for_user(self, *, tenant_context, user_id: str):
        return None


class _StubAuditPort:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def emit(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        return event


def _build_cell(
    *,
    structured_output: _StubStructuredOutput,
    reader: _StubMirrorReader,
    pending_reader: _StubPendingReader | None = None,
    pending_repo: _StubPendingRepo | None = None,
    prior_focus: ArtefactCitation | None = None,
) -> MirrorConversationCell:
    return MirrorConversationCell(
        structured_output_port=structured_output,
        mirror_portfolio_reader=reader,
        actor=_actor(),
        confidence_calculator=_StubConfidenceCalc(),
        threshold_resolver=SinglePairThresholdResolverAdapter(
            thresholds=ConfidenceThresholds(high=0.8, medium=0.5),
        ),
        pending_clarification_reader=(
            pending_reader or _StubPendingReader()
        ),
        pending_clarification_repository=(
            pending_repo or _StubPendingRepo()
        ),
        audit_port=_StubAuditPort(),
        prior_focus=prior_focus,
        originating_intake_id=uuid4(),
        clock=lambda: datetime(2026, 5, 27, 14, 30, tzinfo=timezone.utc),
    )


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _open_and_turn(cell: MirrorConversationCell, text: str):
    async def _drive():
        state = await cell.open(
            ConversationInvocation(
                purpose="mirror_query", actor_id="mirror-test-actor"
            )
        )
        return await cell.turn(state, ConversationInput(text=text))

    return _run(_drive())


# ----------------------------------------------------------- list cases


def test_list_cases_renders_listing_and_cites_each_case() -> None:
    cases = (_summary("Q3 review"), _summary("Acme deal"))
    cell = _build_cell(
        structured_output=_StubStructuredOutput(
            {"intent_class": "list_cases", "confidence": 0.95},
        ),
        reader=_StubMirrorReader(cases=cases),
    )
    state = _open_and_turn(cell, "list my cases")
    response: MirrorConversationResponse = state.payload["mirror_response"]
    assert "Q3 review" in response.text
    assert "Acme deal" in response.text
    assert len(response.cited_artefacts) == 2
    assert all(c.artefact_type == "case" for c in response.cited_artefacts)
    # ListCases responses do not anchor a single focus.
    assert response.current_focus_artefact is None


# ----------------------------------------------------------- show case


def test_show_case_resolves_by_title_and_sets_focus() -> None:
    detail = _detail("revenue", "latency")
    cell = _build_cell(
        structured_output=_StubStructuredOutput(
            {
                "intent_class": "show_case",
                "case_reference": detail.case.title,
                "data_point_reference": "",
                "child_reference": "",
                "confidence": 0.95,
                "clarification": "",
            },
        ),
        reader=_StubMirrorReader(
            cases=(detail.case,), detail=detail
        ),
    )
    state = _open_and_turn(cell, f"show me {detail.case.title}")
    response: MirrorConversationResponse = state.payload["mirror_response"]
    assert detail.case.title in response.text
    assert response.current_focus_artefact is not None
    assert response.current_focus_artefact.artefact_type == "case"
    assert response.current_focus_artefact.artefact_id == detail.case.case_id
    # The cell_payload payload key gets serialised on the state.
    payload = state.payload["cell_payload"]
    assert payload is not None
    assert payload["current_focus_artefact"]["artefact_type"] == "case"


# ----------------------------------------------------------- drill-down


def test_drill_down_with_prior_case_focus_resolves_child() -> None:
    detail = _detail("revenue", "latency")
    prior = ArtefactCitation(
        artefact_id=detail.case.case_id, artefact_type="case"
    )
    cell = _build_cell(
        structured_output=_StubStructuredOutput(
            {
                "intent_class": "drill_down_to_child",
                "child_reference": "revenue",
                "case_reference": "",
                "data_point_reference": "",
                "confidence": 0.95,
                "clarification": "",
            },
        ),
        reader=_StubMirrorReader(
            cases=(detail.case,),
            detail=detail,
            data_point=MirrorDataPoint(
                data_point_id=detail.data_points[0].data_point_id,
                case_id=detail.case.case_id,
                data_point_type="GOAL",
                current_value={"text": "5M ARR"},
                created_at=detail.case.created_at,
                revision_count=1,
            ),
        ),
        prior_focus=prior,
    )
    state = _open_and_turn(cell, "tell me about revenue")
    response: MirrorConversationResponse = state.payload["mirror_response"]
    assert "GOAL" in response.text
    assert response.current_focus_artefact is not None
    assert response.current_focus_artefact.artefact_type == "data_point"


def test_drill_down_without_prior_focus_routes_to_clarification() -> None:
    cell = _build_cell(
        structured_output=_StubStructuredOutput(
            {
                "intent_class": "drill_down_to_child",
                "child_reference": "revenue",
                "confidence": 0.95,
            },
        ),
        reader=_StubMirrorReader(cases=()),
        prior_focus=None,
    )
    state = _open_and_turn(cell, "tell me about revenue")
    response: MirrorConversationResponse = state.payload["mirror_response"]
    # No-prior-focus → friendly clarification, no citations.
    assert "recent case" in response.text or "name" in response.text.lower()
    assert state.payload["confidence_band"] == "no_prior_focus"


# ----------------------------------------------------------- resolution-ambig


def test_show_case_resolution_ambiguity_routes_to_pending() -> None:
    """D139 cross-cutting routing: title-ambiguous case → PendingClarification."""
    case_a = _summary("Q3 portfolio review")
    case_b = _summary("Q3 portfolio review")
    repo = _StubPendingRepo()
    cell = _build_cell(
        structured_output=_StubStructuredOutput(
            {
                "intent_class": "show_case",
                "case_reference": "Q3 portfolio review",
                "data_point_reference": "",
                "child_reference": "",
                "confidence": 0.95,
                "clarification": "",
            },
        ),
        reader=_StubMirrorReader(cases=(case_a, case_b)),
        pending_repo=repo,
    )
    state = _open_and_turn(cell, "show me Q3 portfolio review")
    response: MirrorConversationResponse = state.payload["mirror_response"]
    assert state.payload["confidence_band"] == "resolution_ambiguous"
    assert len(repo.saved) == 1
    pending = repo.saved[0]
    assert pending.target_cell == "mirror_conversation"
    assert "resolution_candidates" in pending.proposed_intent
    assert len(response.cited_artefacts) == 2


# ----------------------------------------------------------- unclear


def test_unclear_routes_with_default_clarification() -> None:
    cell = _build_cell(
        structured_output=_StubStructuredOutput(
            {
                "intent_class": "unclear_mirror",
                "clarification": "Which case do you mean?",
                "confidence": 0.0,
            },
        ),
        reader=_StubMirrorReader(),
    )
    state = _open_and_turn(cell, "uh hi")
    response: MirrorConversationResponse = state.payload["mirror_response"]
    assert "Which case do you mean" in response.text
    assert state.payload["confidence_band"] == "low"
    assert response.current_focus_artefact is None


# ----------------------------------------------------------- cited response protocol


def test_every_response_satisfies_cited_response_protocol() -> None:
    """D138 structural enforcement at the cell's response output."""
    cell = _build_cell(
        structured_output=_StubStructuredOutput(
            {"intent_class": "list_cases", "confidence": 0.9},
        ),
        reader=_StubMirrorReader(cases=(_summary(),)),
    )
    state = _open_and_turn(cell, "list my cases")
    assert isinstance(state.payload["mirror_response"], CitedResponse)
