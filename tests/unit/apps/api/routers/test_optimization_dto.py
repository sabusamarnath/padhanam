"""Unit tests for the optimization HTTP DTOs (D112, S42).

Covers the discriminated-union evidence_citations shape (Pydantic v2
``Discriminator("category")``), Recommendation 1:1 mirroring,
OptimizationRun shape with skipped_categories, and the lifecycle
TransitionResponse envelope.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import TypeAdapter

from apps.api.routers._optimization_dto import (
    CategorySkipReasonResponse,
    CostOptimizationCitationResponse,
    EvidenceCitationResponse,
    OptimizationRunListResponse,
    OptimizationRunResponse,
    RecommendationListResponse,
    RecommendationResponse,
    RecommendationStatusTransitionResponse,
    RetrievalStrategyCitationResponse,
    StartOptimizationRunResponse,
    TransitionResponse,
)
from contexts.optimization.domain import (
    CategorySkipReason,
    OptimizationRun,
    OptimizationRunStatus,
    Recommendation,
    RecommendationCategory,
    RecommendationStatus,
    RecommendationStatusTransition,
)
from contexts.optimization.domain.evidence_citation import (
    CaveatAnnotation,
    CostAggregate,
    CostOptimizationEvidenceCitation,
    RetrievalStrategyEvidenceCitation,
    StrategyComparison,
)


_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc)
_TENANT_UUID = UUID("00000000-0000-4000-8000-00000000a001")
_JURISDICTION = "eu-west"


def _make_retrieval_citation() -> RetrievalStrategyEvidenceCitation:
    return RetrievalStrategyEvidenceCitation(
        evaluation_run_id=uuid4(),
        gold_set_id=uuid4(),
        comparison=StrategyComparison(
            strategy_a="vector_only",
            strategy_b="graph_only",
            recall_at_k_delta={1: 0.4, 3: 0.8, 5: 0.867, 10: 1.0},
            precision_at_k_delta={1: 0.4, 3: 0.267, 5: 0.2, 10: 0.1},
        ),
        caveats=(
            CaveatAnnotation(
                strategy_id="graph_only",
                state="all_zero_aggregates",
                caveat_code="infrastructure_substrate_check_required",
            ),
        ),
    )


def _make_cost_citation() -> CostOptimizationEvidenceCitation:
    return CostOptimizationEvidenceCitation(
        run_history_record_ids=(uuid4(), uuid4()),
        cost_aggregate=CostAggregate(
            agent_template_id=uuid4(),
            mean_cost_per_successful_task_usd=Decimal("0.245"),
            time_window_start=_NOW,
            time_window_end=_NOW.replace(day=29),
            n_successful_runs=15,
            n_runs_total=18,
        ),
    )


def _make_recommendation(
    *,
    category: RecommendationCategory = RecommendationCategory.RETRIEVAL_STRATEGY,
    status: RecommendationStatus = RecommendationStatus.GENERATED,
) -> Recommendation:
    citation = (
        _make_retrieval_citation()
        if category is RecommendationCategory.RETRIEVAL_STRATEGY
        else _make_cost_citation()
    )
    return Recommendation(
        id=uuid4(),
        tenant_id=_TENANT_UUID,
        jurisdiction=_JURISDICTION,
        category=category,
        subject="vector_only outperforms graph_only on recall@3",
        text=(
            "vector_only outperforms graph_only by recall@3 delta of 0.8 "
            "absolute on gold-set 3b001430."
        ),
        evidence_citations=(citation,),
        status=status,
        generated_at=_NOW,
        generated_by_run_id=uuid4(),
        last_transition_at=_NOW,
        last_transition_by_user_id=(
            None if status is RecommendationStatus.GENERATED else "cli-operator"
        ),
    )


def _make_optimization_run(status: OptimizationRunStatus) -> OptimizationRun:
    if status is OptimizationRunStatus.RUNNING:
        completed_at: datetime | None = None
    else:
        completed_at = _NOW.replace(second=30)
    return OptimizationRun(
        id=uuid4(),
        tenant_id=_TENANT_UUID,
        jurisdiction=_JURISDICTION,
        invoked_by_user_id="cli-operator",
        invoked_at=_NOW,
        completed_at=completed_at,
        status=status,
        skipped_categories={
            "model_choice": CategorySkipReason(
                reason_code="substrate_gap",
                reason_text="scoring-sheet evaluation runs not present in Phase 1",
            ),
        },
    )


# ---------------------------------------------------------------------------
# Discriminated union: retrieval_strategy citation
# ---------------------------------------------------------------------------


def test_retrieval_strategy_citation_validates_domain_object() -> None:
    citation = _make_retrieval_citation()
    response = RetrievalStrategyCitationResponse.model_validate(citation)
    assert response.category == "retrieval_strategy"
    assert response.evaluation_run_id == citation.evaluation_run_id
    assert response.gold_set_id == citation.gold_set_id
    assert response.comparison.strategy_a == "vector_only"
    assert response.comparison.strategy_b == "graph_only"
    assert response.comparison.recall_at_k_delta[3] == 0.8
    assert len(response.caveats) == 1
    assert response.caveats[0].caveat_code == (
        "infrastructure_substrate_check_required"
    )


def test_retrieval_strategy_citation_serializes_with_category_discriminator() -> None:
    citation = _make_retrieval_citation()
    response = RetrievalStrategyCitationResponse.model_validate(citation)
    payload = json.loads(response.model_dump_json())
    assert payload["category"] == "retrieval_strategy"
    assert payload["comparison"]["recall_at_k_delta"]["3"] == 0.8


# ---------------------------------------------------------------------------
# Discriminated union: cost_optimization citation
# ---------------------------------------------------------------------------


def test_cost_optimization_citation_validates_domain_object() -> None:
    citation = _make_cost_citation()
    response = CostOptimizationCitationResponse.model_validate(citation)
    assert response.category == "cost_optimization"
    assert len(response.run_history_record_ids) == 2
    assert response.cost_aggregate.mean_cost_per_successful_task_usd == Decimal(
        "0.245"
    )
    assert response.cost_aggregate.n_runs_total == 18


def test_cost_optimization_citation_serializes_decimal_as_string() -> None:
    citation = _make_cost_citation()
    response = CostOptimizationCitationResponse.model_validate(citation)
    payload = json.loads(response.model_dump_json())
    assert payload["category"] == "cost_optimization"
    assert payload["cost_aggregate"]["mean_cost_per_successful_task_usd"] == "0.245"


# ---------------------------------------------------------------------------
# Discriminated union: selection by category
# ---------------------------------------------------------------------------


def test_discriminated_union_selects_retrieval_variant() -> None:
    adapter: TypeAdapter[EvidenceCitationResponse] = TypeAdapter(
        EvidenceCitationResponse
    )
    payload = {
        "category": "retrieval_strategy",
        "evaluation_run_id": str(uuid4()),
        "gold_set_id": str(uuid4()),
        "comparison": {
            "strategy_a": "vector_only",
            "strategy_b": "graph_only",
            "recall_at_k_delta": {"1": 0.4, "3": 0.8, "5": 0.867, "10": 1.0},
            "precision_at_k_delta": {"1": 0.4, "3": 0.267, "5": 0.2, "10": 0.1},
        },
        "caveats": [],
    }
    value = adapter.validate_python(payload)
    assert isinstance(value, RetrievalStrategyCitationResponse)
    assert value.comparison.strategy_a == "vector_only"


def test_discriminated_union_selects_cost_variant() -> None:
    adapter: TypeAdapter[EvidenceCitationResponse] = TypeAdapter(
        EvidenceCitationResponse
    )
    payload = {
        "category": "cost_optimization",
        "run_history_record_ids": [str(uuid4())],
        "cost_aggregate": {
            "agent_template_id": str(uuid4()),
            "mean_cost_per_successful_task_usd": "0.42",
            "time_window_start": _NOW.isoformat(),
            "time_window_end": _NOW.replace(day=29).isoformat(),
            "n_successful_runs": 10,
            "n_runs_total": 12,
        },
    }
    value = adapter.validate_python(payload)
    assert isinstance(value, CostOptimizationCitationResponse)


# ---------------------------------------------------------------------------
# Recommendation aggregate
# ---------------------------------------------------------------------------


def test_recommendation_response_validates_domain_object() -> None:
    recommendation = _make_recommendation()
    response = RecommendationResponse.model_validate(recommendation)
    assert response.category == "retrieval_strategy"
    assert response.status == "generated"
    assert response.subject == recommendation.subject
    assert response.text == recommendation.text
    assert len(response.evidence_citations) == 1
    citation = response.evidence_citations[0]
    assert isinstance(citation, RetrievalStrategyCitationResponse)
    assert citation.comparison.strategy_a == "vector_only"


def test_recommendation_response_renders_acknowledged_status() -> None:
    recommendation = _make_recommendation(
        status=RecommendationStatus.ACKNOWLEDGED
    )
    response = RecommendationResponse.model_validate(recommendation)
    assert response.status == "acknowledged"
    assert response.last_transition_by_user_id == "cli-operator"


def test_recommendation_response_serializes_full_payload() -> None:
    recommendation = _make_recommendation()
    response = RecommendationResponse.model_validate(recommendation)
    payload = json.loads(response.model_dump_json())
    assert payload["category"] == "retrieval_strategy"
    assert payload["evidence_citations"][0]["category"] == "retrieval_strategy"
    assert (
        payload["evidence_citations"][0]["comparison"]["strategy_a"]
        == "vector_only"
    )


def test_recommendation_list_response_envelope() -> None:
    recs = [_make_recommendation() for _ in range(2)]
    response = RecommendationListResponse(
        items=[RecommendationResponse.model_validate(r) for r in recs],
        next_cursor="opaque-b64",
    )
    assert len(response.items) == 2
    assert response.next_cursor == "opaque-b64"


# ---------------------------------------------------------------------------
# OptimizationRun aggregate
# ---------------------------------------------------------------------------


def test_optimization_run_response_validates_completed_run() -> None:
    run = _make_optimization_run(OptimizationRunStatus.COMPLETED)
    response = OptimizationRunResponse.model_validate(run)
    assert response.status == "completed"
    assert response.completed_at is not None
    assert "model_choice" in response.skipped_categories
    assert (
        response.skipped_categories["model_choice"].reason_code == "substrate_gap"
    )


def test_optimization_run_response_validates_running_run() -> None:
    run = _make_optimization_run(OptimizationRunStatus.RUNNING)
    # Running runs must carry completed_at=None per the domain invariant.
    # The fixture honors that; the response mirror passes it through.
    run = OptimizationRun(
        id=run.id,
        tenant_id=run.tenant_id,
        jurisdiction=run.jurisdiction,
        invoked_by_user_id=run.invoked_by_user_id,
        invoked_at=run.invoked_at,
        completed_at=None,
        status=OptimizationRunStatus.RUNNING,
        skipped_categories={},
    )
    response = OptimizationRunResponse.model_validate(run)
    assert response.status == "running"
    assert response.completed_at is None
    assert response.skipped_categories == {}


def test_start_optimization_run_response_envelope() -> None:
    run = _make_optimization_run(OptimizationRunStatus.COMPLETED)
    rec = _make_recommendation()
    response = StartOptimizationRunResponse(
        run=OptimizationRunResponse.model_validate(run),
        recommendations=[RecommendationResponse.model_validate(rec)],
    )
    payload = json.loads(response.model_dump_json())
    assert payload["run"]["status"] == "completed"
    assert len(payload["recommendations"]) == 1
    assert (
        payload["recommendations"][0]["evidence_citations"][0]["category"]
        == "retrieval_strategy"
    )


def test_optimization_run_list_response_envelope() -> None:
    runs = [
        _make_optimization_run(OptimizationRunStatus.COMPLETED) for _ in range(2)
    ]
    response = OptimizationRunListResponse(
        items=[OptimizationRunResponse.model_validate(r) for r in runs],
        next_cursor=None,
    )
    payload = json.loads(response.model_dump_json())
    assert payload["next_cursor"] is None
    assert len(payload["items"]) == 2


# ---------------------------------------------------------------------------
# Lifecycle transition envelope
# ---------------------------------------------------------------------------


def test_transition_response_envelope() -> None:
    recommendation = _make_recommendation(
        status=RecommendationStatus.ACKNOWLEDGED
    )
    transition = RecommendationStatusTransition(
        id=uuid4(),
        recommendation_id=recommendation.id,
        from_status=RecommendationStatus.GENERATED,
        to_status=RecommendationStatus.ACKNOWLEDGED,
        transitioned_by_user_id="cli-operator",
        transitioned_at=_NOW,
    )
    response = TransitionResponse(
        recommendation=RecommendationResponse.model_validate(recommendation),
        transition=RecommendationStatusTransitionResponse.model_validate(transition),
    )
    payload = json.loads(response.model_dump_json())
    assert payload["recommendation"]["status"] == "acknowledged"
    assert payload["transition"]["from_status"] == "generated"
    assert payload["transition"]["to_status"] == "acknowledged"


def test_category_skip_reason_response_serializes() -> None:
    reason = CategorySkipReason(
        reason_code="substrate_gap",
        reason_text="prompt_revision substrate not present",
    )
    response = CategorySkipReasonResponse.model_validate(reason)
    payload = json.loads(response.model_dump_json())
    assert payload == {
        "reason_code": "substrate_gap",
        "reason_text": "prompt_revision substrate not present",
    }
