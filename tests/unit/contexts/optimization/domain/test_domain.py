"""Unit tests for the optimization domain layer (D111)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from contexts.optimization.domain import (
    CAVEAT_INFRASTRUCTURE_SUBSTRATE_CHECK_REQUIRED,
    CategorySkipReason,
    CaveatAnnotation,
    CostAggregate,
    CostOptimizationEvidenceCitation,
    OptimizationRun,
    OptimizationRunStatus,
    Recommendation,
    RecommendationCandidate,
    RecommendationCategory,
    RecommendationStatus,
    RecommendationStatusTransition,
    RetrievalStrategyEvidenceCitation,
    StrategyComparison,
    can_transition,
)


_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc)


def _retrieval_citation() -> RetrievalStrategyEvidenceCitation:
    return RetrievalStrategyEvidenceCitation(
        evaluation_run_id=uuid4(),
        gold_set_id=uuid4(),
        comparison=StrategyComparison(
            strategy_a="graph_only",
            strategy_b="vector_only",
            recall_at_k_delta={1: 0.4, 3: 0.8, 5: 0.87, 10: 1.0},
            precision_at_k_delta={1: 1.0, 3: 0.67, 5: 0.47, 10: 0.3},
        ),
    )


def _cost_citation() -> CostOptimizationEvidenceCitation:
    return CostOptimizationEvidenceCitation(
        run_history_record_ids=(uuid4(), uuid4()),
        cost_aggregate=CostAggregate(
            agent_template_id=uuid4(),
            mean_cost_per_successful_task_usd=Decimal("0.12"),
            time_window_start=_NOW,
            time_window_end=_NOW,
            n_successful_runs=10,
            n_runs_total=12,
        ),
    )


# ----------------------------------------------------------------------
# OptimizationRun
# ----------------------------------------------------------------------


def test_optimization_run_running_requires_no_completed_at() -> None:
    with pytest.raises(ValueError, match="completed_at must be None"):
        OptimizationRun(
            id=uuid4(),
            tenant_id=uuid4(),
            jurisdiction="GB",
            invoked_by_user_id="user-1",
            invoked_at=_NOW,
            completed_at=_NOW,
            status=OptimizationRunStatus.RUNNING,
        )


def test_optimization_run_completed_requires_completed_at() -> None:
    with pytest.raises(ValueError, match="completed_at must be set"):
        OptimizationRun(
            id=uuid4(),
            tenant_id=uuid4(),
            jurisdiction="GB",
            invoked_by_user_id="user-1",
            invoked_at=_NOW,
            completed_at=None,
            status=OptimizationRunStatus.COMPLETED,
        )


def test_optimization_run_skipped_categories_defaults_empty() -> None:
    run = OptimizationRun(
        id=uuid4(),
        tenant_id=uuid4(),
        jurisdiction="GB",
        invoked_by_user_id="user-1",
        invoked_at=_NOW,
        completed_at=None,
        status=OptimizationRunStatus.RUNNING,
    )
    assert run.skipped_categories == {}
    assert run.is_terminal is False


def test_optimization_run_terminal_flag() -> None:
    completed = OptimizationRun(
        id=uuid4(),
        tenant_id=uuid4(),
        jurisdiction="GB",
        invoked_by_user_id="user-1",
        invoked_at=_NOW,
        completed_at=_NOW,
        status=OptimizationRunStatus.COMPLETED,
    )
    assert completed.is_terminal is True


def test_optimization_run_empty_jurisdiction_raises() -> None:
    with pytest.raises(ValueError, match="jurisdiction"):
        OptimizationRun(
            id=uuid4(),
            tenant_id=uuid4(),
            jurisdiction="   ",
            invoked_by_user_id="user-1",
            invoked_at=_NOW,
            completed_at=None,
            status=OptimizationRunStatus.RUNNING,
        )


def test_optimization_run_skipped_categories_carries_structure() -> None:
    skipped = {
        "model_choice": CategorySkipReason(
            reason_code="substrate_gap",
            reason_text="scoring-sheet evaluation runs not present in Phase 1",
        )
    }
    run = OptimizationRun(
        id=uuid4(),
        tenant_id=uuid4(),
        jurisdiction="GB",
        invoked_by_user_id="user-1",
        invoked_at=_NOW,
        completed_at=_NOW,
        status=OptimizationRunStatus.COMPLETED,
        skipped_categories=skipped,
    )
    assert run.skipped_categories["model_choice"].reason_code == "substrate_gap"


# ----------------------------------------------------------------------
# Recommendation
# ----------------------------------------------------------------------


def test_recommendation_generated_status_forbids_transition_user() -> None:
    with pytest.raises(ValueError, match="last_transition_by_user_id must be None"):
        Recommendation(
            id=uuid4(),
            tenant_id=uuid4(),
            jurisdiction="GB",
            category=RecommendationCategory.RETRIEVAL_STRATEGY,
            subject="vector_only vs graph_only",
            text="Switch from graph_only to vector_only.",
            evidence_citations=(_retrieval_citation(),),
            status=RecommendationStatus.GENERATED,
            generated_at=_NOW,
            generated_by_run_id=uuid4(),
            last_transition_at=_NOW,
            last_transition_by_user_id="user-1",
        )


def test_recommendation_post_generation_requires_transition_user() -> None:
    with pytest.raises(ValueError, match="last_transition_by_user_id must be set"):
        Recommendation(
            id=uuid4(),
            tenant_id=uuid4(),
            jurisdiction="GB",
            category=RecommendationCategory.RETRIEVAL_STRATEGY,
            subject="vector_only vs graph_only",
            text="Switch from graph_only to vector_only.",
            evidence_citations=(_retrieval_citation(),),
            status=RecommendationStatus.ACKNOWLEDGED,
            generated_at=_NOW,
            generated_by_run_id=uuid4(),
            last_transition_at=_NOW,
            last_transition_by_user_id=None,
        )


def test_recommendation_requires_matching_citation_category() -> None:
    with pytest.raises(ValueError, match="matching category"):
        Recommendation(
            id=uuid4(),
            tenant_id=uuid4(),
            jurisdiction="GB",
            category=RecommendationCategory.RETRIEVAL_STRATEGY,
            subject="bogus",
            text="x",
            evidence_citations=(_cost_citation(),),
            status=RecommendationStatus.GENERATED,
            generated_at=_NOW,
            generated_by_run_id=uuid4(),
            last_transition_at=_NOW,
            last_transition_by_user_id=None,
        )


def test_recommendation_requires_non_empty_citations() -> None:
    with pytest.raises(ValueError, match="evidence_citations must not be empty"):
        Recommendation(
            id=uuid4(),
            tenant_id=uuid4(),
            jurisdiction="GB",
            category=RecommendationCategory.RETRIEVAL_STRATEGY,
            subject="x",
            text="x",
            evidence_citations=(),
            status=RecommendationStatus.GENERATED,
            generated_at=_NOW,
            generated_by_run_id=uuid4(),
            last_transition_at=_NOW,
            last_transition_by_user_id=None,
        )


def test_recommendation_terminal_flag() -> None:
    rec = Recommendation(
        id=uuid4(),
        tenant_id=uuid4(),
        jurisdiction="GB",
        category=RecommendationCategory.RETRIEVAL_STRATEGY,
        subject="x",
        text="x",
        evidence_citations=(_retrieval_citation(),),
        status=RecommendationStatus.APPLIED,
        generated_at=_NOW,
        generated_by_run_id=uuid4(),
        last_transition_at=_NOW,
        last_transition_by_user_id="user-1",
    )
    assert rec.is_terminal is True


# ----------------------------------------------------------------------
# Status transitions
# ----------------------------------------------------------------------


def test_can_transition_generated_to_any_user_state() -> None:
    assert can_transition(
        from_status=RecommendationStatus.GENERATED,
        to_status=RecommendationStatus.ACKNOWLEDGED,
    )
    assert can_transition(
        from_status=RecommendationStatus.GENERATED,
        to_status=RecommendationStatus.APPLIED,
    )
    assert can_transition(
        from_status=RecommendationStatus.GENERATED,
        to_status=RecommendationStatus.REJECTED,
    )


def test_can_transition_acknowledged_only_to_apply_or_reject() -> None:
    assert can_transition(
        from_status=RecommendationStatus.ACKNOWLEDGED,
        to_status=RecommendationStatus.APPLIED,
    )
    assert can_transition(
        from_status=RecommendationStatus.ACKNOWLEDGED,
        to_status=RecommendationStatus.REJECTED,
    )
    assert not can_transition(
        from_status=RecommendationStatus.ACKNOWLEDGED,
        to_status=RecommendationStatus.GENERATED,
    )


def test_can_transition_terminal_states_forbid_any_transition() -> None:
    for state in (RecommendationStatus.APPLIED, RecommendationStatus.REJECTED):
        for target in RecommendationStatus:
            assert not can_transition(from_status=state, to_status=target)


def test_status_transition_value_object_requires_distinct_states() -> None:
    with pytest.raises(ValueError, match="must differ"):
        RecommendationStatusTransition(
            id=uuid4(),
            recommendation_id=uuid4(),
            from_status=RecommendationStatus.GENERATED,
            to_status=RecommendationStatus.GENERATED,
            transitioned_by_user_id="user-1",
            transitioned_at=_NOW,
        )


def test_status_transition_value_object_requires_user_id() -> None:
    with pytest.raises(ValueError, match="transitioned_by_user_id"):
        RecommendationStatusTransition(
            id=uuid4(),
            recommendation_id=uuid4(),
            from_status=RecommendationStatus.GENERATED,
            to_status=RecommendationStatus.APPLIED,
            transitioned_by_user_id="",
            transitioned_at=_NOW,
        )


# ----------------------------------------------------------------------
# Citations and caveats
# ----------------------------------------------------------------------


def test_caveat_annotation_requires_all_fields() -> None:
    with pytest.raises(ValueError, match="strategy_id"):
        CaveatAnnotation(
            strategy_id="",
            state="all_zero_aggregates",
            caveat_code=CAVEAT_INFRASTRUCTURE_SUBSTRATE_CHECK_REQUIRED,
        )


def test_retrieval_strategy_citation_category_property() -> None:
    citation = _retrieval_citation()
    assert citation.category is RecommendationCategory.RETRIEVAL_STRATEGY


def test_cost_optimization_citation_category_property() -> None:
    citation = _cost_citation()
    assert citation.category is RecommendationCategory.COST_OPTIMIZATION


def test_retrieval_citation_with_caveat_preserves_structure() -> None:
    caveat = CaveatAnnotation(
        strategy_id="graph_only",
        state="all_zero_aggregates",
        caveat_code=CAVEAT_INFRASTRUCTURE_SUBSTRATE_CHECK_REQUIRED,
    )
    citation = RetrievalStrategyEvidenceCitation(
        evaluation_run_id=uuid4(),
        gold_set_id=uuid4(),
        comparison=StrategyComparison(
            strategy_a="graph_only",
            strategy_b="vector_only",
            recall_at_k_delta={1: 0.4, 3: 0.8, 5: 0.87, 10: 1.0},
            precision_at_k_delta={1: 1.0, 3: 0.67, 5: 0.47, 10: 0.3},
        ),
        caveats=(caveat,),
    )
    assert citation.caveats[0].caveat_code == (
        CAVEAT_INFRASTRUCTURE_SUBSTRATE_CHECK_REQUIRED
    )


# ----------------------------------------------------------------------
# RecommendationCandidate
# ----------------------------------------------------------------------


def test_recommendation_candidate_requires_text() -> None:
    with pytest.raises(ValueError, match="text"):
        RecommendationCandidate(
            category=RecommendationCategory.RETRIEVAL_STRATEGY,
            subject="x",
            text="",
            evidence_citations=(_retrieval_citation(),),
        )


def test_recommendation_candidate_citation_category_coherence() -> None:
    with pytest.raises(ValueError, match="matching category"):
        RecommendationCandidate(
            category=RecommendationCategory.RETRIEVAL_STRATEGY,
            subject="x",
            text="x",
            evidence_citations=(_cost_citation(),),
        )
