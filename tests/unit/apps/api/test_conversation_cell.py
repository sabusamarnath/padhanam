"""Unit tests for the stateless web ConversationFlow adapter (D158, S59).

Exercises ``apps/api/_conversation_cell_wiring.py`` — the live
conversational-turn-over-HTTP adapter that wires the existing portfolio
mirror-conversation cell — at the wiring layer with stubs, the same shape
the mirror-cell unit tests use. Covers: the opening turn grounds on the
focus Case and resolves citations to human labels (no raw UUID); the
drill-down focus threads through the client ``cell_payload`` statelessly
(no server-side state); resolution-ambiguity routes to clarification (no
silent default); and a turn cannot run on a Case outside the actor's
tenant (isolation invariant at the wiring boundary).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from apps.api import _conversation_cell_wiring as wiring
from contexts.audit.domain.events import AuditEvent
from contexts.messaging.adapters.threshold_single_pair import (
    SinglePairThresholdResolverAdapter,
)
from contexts.mirror_conversation.application.ports.mirror_portfolio_reader import (  # noqa: E501
    MirrorCaseDetail,
    MirrorCaseSummary,
    MirrorDataPoint,
    MirrorDataPointSummary,
)
from contexts.mirror_conversation.application.response import (
    serialise_focus_to_cell_payload,
)
from shared_kernel import (
    ActorContext,
    ConfidenceThresholds,
    StructuredOutputResponse,
    TenantContext,
)
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles
from shared_kernel.conversation_flow import ArtefactCitation

_TENANT_A = "00000000-0000-4000-8000-00000000a001"
_TENANT_B = "00000000-0000-4000-8000-00000000a002"
_NOW = datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc)


def _actor(tenant_id: str = _TENANT_A) -> ActorContext:
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=tenant_id,
            jurisdiction="eu-west",
            cost_attribution_id=tenant_id,
        ),
        actor_id=f"operator-{tenant_id[-1]}",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def _summary(title: str, case_id: UUID | None = None) -> MirrorCaseSummary:
    return MirrorCaseSummary(
        case_id=case_id or uuid4(),
        title=title,
        case_status="OPEN",
        created_at=_NOW,
        last_activity_at=_NOW,
        data_point_count=1,
    )


def _detail(title: str, *dp_labels: str) -> MirrorCaseDetail:
    case = _summary(title)
    dps = tuple(
        MirrorDataPointSummary(
            data_point_id=uuid4(),
            case_id=case.case_id,
            data_point_type="GOAL",
            label=label,
            created_at=_NOW,
        )
        for label in dp_labels
    )
    return MirrorCaseDetail(case=case, data_points=dps)


class _StubReader:
    """Tenant-scoped mirror reader stub: serves data only for its tenant."""

    def __init__(
        self,
        *,
        tenant_id: str,
        cases: tuple[MirrorCaseSummary, ...] = (),
        detail: MirrorCaseDetail | None = None,
        data_point: MirrorDataPoint | None = None,
    ) -> None:
        self._tenant_id = tenant_id
        self._cases = cases
        self._detail = detail
        self._data_point = data_point

    def _scoped(self, actor: ActorContext) -> bool:
        return str(actor.tenant_context.tenant_id) == self._tenant_id

    async def list_cases(self, *, actor: ActorContext, limit: int = 50):
        return self._cases if self._scoped(actor) else ()

    async def find_cases(self, *, actor: ActorContext):
        return self._cases if self._scoped(actor) else ()

    async def get_case_detail(self, *, actor: ActorContext, case_id: UUID):
        if not self._scoped(actor) or self._detail is None:
            return None
        return self._detail if self._detail.case.case_id == case_id else None

    async def get_data_point(self, *, actor: ActorContext, data_point_id: UUID):
        return self._data_point if self._scoped(actor) else None


class _StubStructuredOutput:
    def __init__(self, value: dict[str, Any], *, confidence: float = 0.95):
        self._value = value
        self._confidence = confidence

    async def generate_structured(self, request: Any):
        return StructuredOutputResponse(
            value=self._value, confidence=self._confidence, provider_metadata={}
        )


class _StubConfidence:
    def compute(self, *, request: Any, response: Any) -> float:
        return float(getattr(response, "confidence", 0.0) or 0.0)


class _StubPendingReader:
    async def get_active(self, *, tenant_id, user_id: str):
        return None


class _StubPendingRepo:
    def __init__(self) -> None:
        self.saved: list[Any] = []

    async def save(self, *, tenant_context, pending) -> None:
        self.saved.append(pending)

    async def update_status(self, *, tenant_context, pending) -> None:
        return None

    async def get_by_id(self, *, tenant_context, pending_id):
        return None

    async def get_active_for_user(self, *, tenant_context, user_id: str):
        return None


class _StubAudit:
    async def emit(self, event: AuditEvent) -> AuditEvent:
        return event


class _FakeMessaging:
    """The cell collaborators the wiring reads off MessagingComposition."""

    def __init__(self, *, reader: _StubReader, structured: _StubStructuredOutput):
        self.mirror_portfolio_reader = reader
        self.structured_output_port = structured
        self.confidence_calculator = _StubConfidence()
        self.threshold_resolver = SinglePairThresholdResolverAdapter(
            thresholds=ConfidenceThresholds(high=0.8, medium=0.5),
        )
        self.pending_clarification_reader = _StubPendingReader()
        self.pending_clarification_repository = _StubPendingRepo()


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


# ------------------------------------------------------------------- open


def test_open_grounds_on_focus_case_and_resolves_citations() -> None:
    detail = _detail("Q3 portfolio review", "revenue target")
    reader = _StubReader(
        tenant_id=_TENANT_A,
        cases=(detail.case,),
        detail=detail,
        data_point=MirrorDataPoint(
            data_point_id=detail.data_points[0].data_point_id,
            case_id=detail.case.case_id,
            data_point_type="GOAL",
            current_value={"text": "5M ARR"},
            created_at=_NOW,
            revision_count=1,
        ),
    )
    messaging = _FakeMessaging(
        reader=reader,
        structured=_StubStructuredOutput(
            {
                "intent_class": "show_case",
                "case_reference": "Q3 portfolio review",
                "data_point_reference": "",
                "child_reference": "",
                "confidence": 0.95,
                "clarification": "",
            }
        ),
    )
    result = _run(
        wiring.open_conversation(
            messaging=messaging,
            audit_port=_StubAudit(),
            actor=_actor(),
            focus_id=detail.case.case_id,
        )
    )
    assert result is not None
    # The opening assistant turn presents the clicked Case.
    assert "Q3 portfolio review" in result.reply
    assert result.turn_count == 1
    assert result.is_open is True
    # The focus threads back to the client via cell_payload (D141).
    assert result.cell_payload is not None
    assert result.cell_payload["current_focus_artefact"]["artefact_type"] == "case"
    # Citations resolve to source-typed human labels — no raw UUID.
    types = {c.type for c in result.citations}
    assert "case" in types
    case_chip = next(c for c in result.citations if c.type == "case")
    assert case_chip.label == "Q3 portfolio review"
    full_uuid = str(detail.case.case_id)
    for c in result.citations:
        assert full_uuid not in c.label
        assert full_uuid not in c.ref
        assert len(c.ref) == 8  # short-hex, not the raw id


def test_open_on_missing_case_returns_none() -> None:
    reader = _StubReader(tenant_id=_TENANT_A, detail=None)
    messaging = _FakeMessaging(
        reader=reader,
        structured=_StubStructuredOutput({"intent_class": "unclear_mirror"}),
    )
    result = _run(
        wiring.open_conversation(
            messaging=messaging,
            audit_port=_StubAudit(),
            actor=_actor(),
            focus_id=uuid4(),
        )
    )
    assert result is None


# ------------------------------------------------------ tenant isolation


def test_turn_cannot_open_a_case_outside_the_actors_tenant() -> None:
    """A tenant_b actor cannot open tenant_a's Case (isolation invariant)."""
    detail = _detail("Tenant A only", "secret")
    reader = _StubReader(  # the reader is tenant_a-scoped
        tenant_id=_TENANT_A, cases=(detail.case,), detail=detail
    )
    messaging = _FakeMessaging(
        reader=reader,
        structured=_StubStructuredOutput({"intent_class": "unclear_mirror"}),
    )
    result = _run(
        wiring.open_conversation(
            messaging=messaging,
            audit_port=_StubAudit(),
            actor=_actor(_TENANT_B),  # the foreign actor
            focus_id=detail.case.case_id,
        )
    )
    # No turn runs on the foreign item; the route maps None -> 404.
    assert result is None


# ----------------------------------------------------- drill-down threading


def test_advance_threads_drilldown_focus_through_the_client() -> None:
    """The prior focus arrives via the client cell_payload, not server state."""
    detail = _detail("Q3 portfolio review", "revenue")
    reader = _StubReader(
        tenant_id=_TENANT_A,
        cases=(detail.case,),
        detail=detail,
        data_point=MirrorDataPoint(
            data_point_id=detail.data_points[0].data_point_id,
            case_id=detail.case.case_id,
            data_point_type="GOAL",
            current_value={"text": "5M ARR"},
            created_at=_NOW,
            revision_count=1,
        ),
    )
    messaging = _FakeMessaging(
        reader=reader,
        structured=_StubStructuredOutput(
            {
                "intent_class": "drill_down_to_child",
                "child_reference": "revenue",
                "case_reference": "",
                "data_point_reference": "",
                "confidence": 0.95,
                "clarification": "",
            }
        ),
    )
    # The client threads back the prior turn's focus (the case).
    prior_payload = serialise_focus_to_cell_payload(
        ArtefactCitation(artefact_id=detail.case.case_id, artefact_type="case")
    )
    result = _run(
        wiring.advance_conversation(
            messaging=messaging,
            audit_port=_StubAudit(),
            actor=_actor(),
            conversation_id="conv-1",
            purpose="mirror_query",
            turn_count=1,
            cell_payload=prior_payload,
            text="tell me about revenue",
        )
    )
    assert "GOAL" in result.reply
    assert result.conversation_id == "conv-1"
    assert result.turn_count == 2
    # The focus advanced to the data point — drill-down worked statelessly.
    assert result.cell_payload["current_focus_artefact"]["artefact_type"] == (
        "data_point"
    )


def test_advance_without_prior_focus_clarifies_not_silently_defaults() -> None:
    reader = _StubReader(tenant_id=_TENANT_A, cases=())
    messaging = _FakeMessaging(
        reader=reader,
        structured=_StubStructuredOutput(
            {"intent_class": "drill_down_to_child", "child_reference": "revenue"}
        ),
    )
    result = _run(
        wiring.advance_conversation(
            messaging=messaging,
            audit_port=_StubAudit(),
            actor=_actor(),
            conversation_id="conv-1",
            purpose="mirror_query",
            turn_count=1,
            cell_payload=None,  # no threaded focus
            text="tell me about revenue",
        )
    )
    # No-prior-focus → clarification, never a silent guess.
    assert "name" in result.reply.lower() or "recent case" in result.reply


# ----------------------------------------------------- clarification routing


def test_ambiguous_reference_routes_to_clarification() -> None:
    """D139: a title matching multiple Cases clarifies, no silent default."""
    case_a = _summary("Q3 portfolio review")
    case_b = _summary("Q3 portfolio review")
    messaging = _FakeMessaging(
        reader=_StubReader(tenant_id=_TENANT_A, cases=(case_a, case_b)),
        structured=_StubStructuredOutput(
            {
                "intent_class": "show_case",
                "case_reference": "Q3 portfolio review",
                "data_point_reference": "",
                "child_reference": "",
                "confidence": 0.95,
                "clarification": "",
            }
        ),
    )
    result = _run(
        wiring.advance_conversation(
            messaging=messaging,
            audit_port=_StubAudit(),
            actor=_actor(),
            conversation_id="conv-1",
            purpose="mirror_query",
            turn_count=1,
            cell_payload=None,
            text="show me Q3 portfolio review",
        )
    )
    assert "Which did you mean" in result.reply
    # The candidate cases are cited so the operator sees what they pick among.
    assert len([c for c in result.citations if c.type == "case"]) == 2
