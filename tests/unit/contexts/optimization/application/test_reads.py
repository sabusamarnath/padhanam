"""Unit tests for the read use cases (get/list)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from contexts.optimization.application import (
    get_optimization_run,
    get_recommendation,
    list_optimization_runs,
    list_recommendations,
)
from contexts.optimization.domain import (
    OptimizationRun,
    OptimizationRunStatus,
    Recommendation,
    RecommendationCategory,
    RecommendationStatus,
    RetrievalStrategyEvidenceCitation,
    StrategyComparison,
)
from contexts.optimization.domain.query_filters import (
    RecommendationListFilters,
)
from shared_kernel.tenant_context import TenantContext
from tests.unit.contexts.optimization.application._fakes import (
    FakeOptimizationRunReader,
    FakeOptimizationRunRepository,
    FakeRecommendationReader,
    FakeRecommendationRepository,
)


_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc)
_TENANT_A = "00000000-0000-0000-0000-00000000a000"


def _tenant_ctx() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_A,
        jurisdiction="GB",
        cost_attribution_id="cost-attr-1",
    )


def _citation() -> RetrievalStrategyEvidenceCitation:
    return RetrievalStrategyEvidenceCitation(
        evaluation_run_id=uuid4(),
        gold_set_id=uuid4(),
        comparison=StrategyComparison(
            strategy_a="a",
            strategy_b="b",
            recall_at_k_delta={1: 0.0, 3: 0.5, 5: 0.5, 10: 0.5},
            precision_at_k_delta={1: 0.0, 3: 0.0, 5: 0.0, 10: 0.0},
        ),
    )


def _recommendation(
    *,
    category: RecommendationCategory = RecommendationCategory.RETRIEVAL_STRATEGY,
    status: RecommendationStatus = RecommendationStatus.GENERATED,
) -> Recommendation:
    return Recommendation(
        id=uuid4(),
        tenant_id=UUID(_TENANT_A),
        jurisdiction="GB",
        category=category,
        subject="x",
        text="x",
        evidence_citations=(_citation(),),
        status=status,
        generated_at=_NOW,
        generated_by_run_id=uuid4(),
        last_transition_at=_NOW,
        last_transition_by_user_id="u" if status != RecommendationStatus.GENERATED else None,
    )


def _run() -> OptimizationRun:
    return OptimizationRun(
        id=uuid4(),
        tenant_id=UUID(_TENANT_A),
        jurisdiction="GB",
        invoked_by_user_id="u",
        invoked_at=_NOW,
        completed_at=_NOW,
        status=OptimizationRunStatus.COMPLETED,
    )


def test_get_recommendation_returns_record() -> None:
    rec = _recommendation()
    repo = FakeRecommendationRepository(recommendations={rec.id: rec})
    reader = FakeRecommendationReader(repository=repo)
    fetched = asyncio.run(
        get_recommendation(
            tenant_context=_tenant_ctx(),
            recommendation_id=rec.id,
            reader=reader,
        )
    )
    assert fetched == rec


def test_get_recommendation_missing_returns_none() -> None:
    repo = FakeRecommendationRepository()
    reader = FakeRecommendationReader(repository=repo)
    fetched = asyncio.run(
        get_recommendation(
            tenant_context=_tenant_ctx(),
            recommendation_id=uuid4(),
            reader=reader,
        )
    )
    assert fetched is None


def test_list_recommendations_filters_by_category() -> None:
    from decimal import Decimal

    from contexts.optimization.domain import (
        CostAggregate,
        CostOptimizationEvidenceCitation,
    )

    rec_a = _recommendation(category=RecommendationCategory.RETRIEVAL_STRATEGY)
    cost_citation = CostOptimizationEvidenceCitation(
        run_history_record_ids=(uuid4(),),
        cost_aggregate=CostAggregate(
            agent_template_id=uuid4(),
            mean_cost_per_successful_task_usd=Decimal("0.20"),
            time_window_start=_NOW,
            time_window_end=_NOW,
            n_successful_runs=1,
            n_runs_total=1,
        ),
    )
    rec_b = Recommendation(
        id=uuid4(),
        tenant_id=UUID(_TENANT_A),
        jurisdiction="GB",
        category=RecommendationCategory.COST_OPTIMIZATION,
        subject="x",
        text="x",
        evidence_citations=(cost_citation,),
        status=RecommendationStatus.GENERATED,
        generated_at=_NOW,
        generated_by_run_id=uuid4(),
        last_transition_at=_NOW,
        last_transition_by_user_id=None,
    )
    repo = FakeRecommendationRepository(
        recommendations={rec_a.id: rec_a, rec_b.id: rec_b}
    )
    reader = FakeRecommendationReader(repository=repo)
    page, next_cursor = asyncio.run(
        list_recommendations(
            tenant_context=_tenant_ctx(),
            reader=reader,
            filters=RecommendationListFilters(
                categories=(RecommendationCategory.RETRIEVAL_STRATEGY,),
            ),
            encoded_cursor=None,
            page_size=10,
        )
    )
    assert next_cursor is None
    assert len(page.recommendations) == 1
    assert page.recommendations[0].id == rec_a.id


def test_list_recommendations_page_size_validation_rejects_out_of_range() -> None:
    repo = FakeRecommendationRepository()
    reader = FakeRecommendationReader(repository=repo)
    with pytest.raises(ValueError, match="page_size"):
        asyncio.run(
            list_recommendations(
                tenant_context=_tenant_ctx(),
                reader=reader,
                filters=RecommendationListFilters(),
                encoded_cursor=None,
                page_size=0,
            )
        )
    with pytest.raises(ValueError, match="page_size"):
        asyncio.run(
            list_recommendations(
                tenant_context=_tenant_ctx(),
                reader=reader,
                filters=RecommendationListFilters(),
                encoded_cursor=None,
                page_size=99,
            )
        )


def test_get_optimization_run_returns_snapshot() -> None:
    run = _run()
    repo = FakeOptimizationRunRepository(runs={run.id: run})
    reader = FakeOptimizationRunReader(repository=repo)
    snapshot = asyncio.run(
        get_optimization_run(
            tenant_context=_tenant_ctx(),
            run_id=run.id,
            reader=reader,
        )
    )
    assert snapshot is not None
    assert snapshot.run == run


def test_list_optimization_runs_paginated_default_page_size() -> None:
    run = _run()
    repo = FakeOptimizationRunRepository(runs={run.id: run})
    reader = FakeOptimizationRunReader(repository=repo)
    page, next_cursor = asyncio.run(
        list_optimization_runs(
            tenant_context=_tenant_ctx(),
            reader=reader,
            encoded_cursor=None,
            page_size=10,
        )
    )
    assert next_cursor is None
    assert len(page.runs) == 1
