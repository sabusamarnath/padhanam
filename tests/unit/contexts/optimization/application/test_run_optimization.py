"""Unit tests for the run_optimization engine (D111 cmt 2, 5, 8)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable
from uuid import UUID, uuid4

import pytest

from contexts.optimization.application import (
    EvidenceContext,
    RunOptimizationResult,
    run_optimization,
)
from contexts.optimization.application.audit_events import (
    ACTION_OPTIMIZATION_RUN_COMPLETE,
    ACTION_OPTIMIZATION_RUN_FAIL,
    ACTION_OPTIMIZATION_RUN_START,
    ACTION_RECOMMENDATION_GENERATE,
)
from contexts.optimization.application.rules import default_rules
from contexts.optimization.domain import (
    CategorySkipReason,
    OptimizationRunStatus,
    RecommendationCandidate,
    RecommendationCategory,
    RetrievalStrategyEvidenceCitation,
    StrategyComparison,
    SubstrateGapError,
)
from contexts.retrieval_evaluation.domain import (
    EvaluationAggregate,
    EvaluationRun,
    EvaluationRunStatus,
)
from shared_kernel.tenant_context import TenantContext
from tests.unit.contexts.optimization.application._fakes import (
    FakeAuditEventReader,
    FakeEvaluationRunReader,
    FakeGoldSetReader,
    FakeOptimizationRunReader,
    FakeOptimizationRunRepository,
    FakeRecommendationReader,
    FakeRecommendationRepository,
    FakeRunHistoryReader,
    RecordingAuditPort,
)


_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc)
_TENANT_A = "00000000-0000-0000-0000-00000000a000"
_TENANT_B = "00000000-0000-0000-0000-00000000b000"


def _tenant_ctx(tenant_id: str = _TENANT_A) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        jurisdiction="GB",
        cost_attribution_id="cost-attr-1",
    )


def _empty_evidence_context(
    tenant: TenantContext | None = None,
) -> EvidenceContext:
    return EvidenceContext(
        tenant_context=tenant or _tenant_ctx(),
        evaluation_run_reader=FakeEvaluationRunReader(),
        run_history_reader=FakeRunHistoryReader(),
        gold_set_reader=FakeGoldSetReader(),
        audit_event_reader=FakeAuditEventReader(),
    )


def _evaluation_evidence_context(
    *,
    runs_and_aggregates: list[
        tuple[EvaluationRun, tuple[EvaluationAggregate, ...]]
    ],
) -> EvidenceContext:
    reader = FakeEvaluationRunReader(
        runs=[r for r, _ in runs_and_aggregates],
        aggregates={r.id: aggs for r, aggs in runs_and_aggregates},
    )
    return EvidenceContext(
        tenant_context=_tenant_ctx(),
        evaluation_run_reader=reader,
        run_history_reader=FakeRunHistoryReader(),
        gold_set_reader=FakeGoldSetReader(),
        audit_event_reader=FakeAuditEventReader(),
    )


def _aggregate(
    *,
    run_id: UUID,
    strategy: str,
    recall_at_3: float,
) -> EvaluationAggregate:
    return EvaluationAggregate(
        id=uuid4(),
        evaluation_run_id=run_id,
        retrieval_strategy=strategy,
        recall_at_k_mean={1: 0.0, 3: recall_at_3, 5: recall_at_3, 10: 1.0},
        precision_at_k_mean={1: 0.5, 3: 0.5, 5: 0.5, 10: 0.5},
        mrr_mean=Decimal("1.0000"),
        latency_ms_p50=100,
        latency_ms_p95=200,
        latency_ms_mean=120,
    )


def _eval_run(
    *,
    tenant_id: str = _TENANT_A,
) -> EvaluationRun:
    return EvaluationRun(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        jurisdiction="GB",
        gold_set_id=uuid4(),
        gold_set_revision_id=uuid4(),
        invoked_by_user_id="cli-operator",
        invoked_at=_NOW,
        completed_at=_NOW,
        status=EvaluationRunStatus.COMPLETED,
    )


# ----------------------------------------------------------------------
# Default rule wiring
# ----------------------------------------------------------------------


def test_engine_completes_with_default_rules_and_no_evidence() -> None:
    """No evidence → no recommendations + skip-reasons for Phase 1 zeros."""
    run_repo = FakeOptimizationRunRepository()
    rec_repo = FakeRecommendationRepository()
    audit = RecordingAuditPort()
    result = asyncio.run(
        run_optimization(
            tenant_context=_tenant_ctx(),
            invoked_by_user_id="cli-operator",
            rules=default_rules(),
            evidence_context=_empty_evidence_context(),
            optimization_run_repository=run_repo,
            recommendation_repository=rec_repo,
            audit_port=audit,
            now=_NOW,
        )
    )
    assert isinstance(result, RunOptimizationResult)
    assert result.run.status is OptimizationRunStatus.COMPLETED
    assert result.recommendations == ()
    assert set(result.skipped_categories.keys()) == {"model_choice", "prompt_revision"}
    for reason in result.skipped_categories.values():
        assert reason.reason_code == "substrate_gap"


def test_engine_emits_run_start_and_complete_audit_events() -> None:
    audit = RecordingAuditPort()
    asyncio.run(
        run_optimization(
            tenant_context=_tenant_ctx(),
            invoked_by_user_id="cli-operator",
            rules=default_rules(),
            evidence_context=_empty_evidence_context(),
            optimization_run_repository=FakeOptimizationRunRepository(),
            recommendation_repository=FakeRecommendationRepository(),
            audit_port=audit,
            now=_NOW,
        )
    )
    actions = [e.action_verb for e in audit.events]
    assert actions[0] == ACTION_OPTIMIZATION_RUN_START
    assert actions[-1] == ACTION_OPTIMIZATION_RUN_COMPLETE
    # skipped_categories embedded in the complete event's after_state
    terminal_event = audit.events[-1]
    skipped = terminal_event.after_state["skipped_categories"]
    assert set(skipped.keys()) == {"model_choice", "prompt_revision"}


def test_engine_generates_recommendations_from_retrieval_strategy_rule() -> None:
    run = _eval_run()
    aggregates = (
        _aggregate(run_id=run.id, strategy="graph_only", recall_at_3=0.0),
        _aggregate(run_id=run.id, strategy="vector_only", recall_at_3=0.8),
    )
    evidence = _evaluation_evidence_context(
        runs_and_aggregates=[(run, aggregates)]
    )
    audit = RecordingAuditPort()
    rec_repo = FakeRecommendationRepository()
    result = asyncio.run(
        run_optimization(
            tenant_context=_tenant_ctx(),
            invoked_by_user_id="cli-operator",
            rules=default_rules(),
            evidence_context=evidence,
            optimization_run_repository=FakeOptimizationRunRepository(),
            recommendation_repository=rec_repo,
            audit_port=audit,
            now=_NOW,
        )
    )
    assert len(result.recommendations) == 1
    persisted = list(rec_repo.recommendations.values())[0]
    assert persisted.category is RecommendationCategory.RETRIEVAL_STRATEGY
    assert (
        persisted.generated_by_run_id == result.run.id
    )
    generate_events = [
        e
        for e in audit.events
        if e.action_verb == ACTION_RECOMMENDATION_GENERATE
    ]
    assert len(generate_events) == 1
    # full citation embedded in after_state per Finding 4 disposition
    citation_payload = generate_events[0].after_state["evidence_citations"]
    assert isinstance(citation_payload, list)
    assert citation_payload[0]["category"] == "retrieval_strategy"
    assert "comparison" in citation_payload[0]


# ----------------------------------------------------------------------
# Failure path
# ----------------------------------------------------------------------


class _ExplodingRule:
    category = RecommendationCategory.RETRIEVAL_STRATEGY

    async def evaluate(self, *, evidence_context):
        raise RuntimeError("rule exploded")


def test_engine_marks_failed_on_uncaught_exception_and_reraises() -> None:
    run_repo = FakeOptimizationRunRepository()
    audit = RecordingAuditPort()
    with pytest.raises(RuntimeError, match="rule exploded"):
        asyncio.run(
            run_optimization(
                tenant_context=_tenant_ctx(),
                invoked_by_user_id="cli-operator",
                rules=(_ExplodingRule(),),
                evidence_context=_empty_evidence_context(),
                optimization_run_repository=run_repo,
                recommendation_repository=FakeRecommendationRepository(),
                audit_port=audit,
                now=_NOW,
            )
        )
    stored = list(run_repo.runs.values())
    assert len(stored) == 1
    assert stored[0].status is OptimizationRunStatus.FAILED
    assert stored[0].completed_at is not None
    actions = [e.action_verb for e in audit.events]
    assert actions == [
        ACTION_OPTIMIZATION_RUN_START,
        ACTION_OPTIMIZATION_RUN_FAIL,
    ]


# ----------------------------------------------------------------------
# Substrate-gap handling
# ----------------------------------------------------------------------


class _SubstrateGapRule:
    category = RecommendationCategory.MODEL_CHOICE

    async def evaluate(self, *, evidence_context):
        raise SubstrateGapError(
            category=self.category,
            reason=CategorySkipReason(
                reason_code="custom_gap",
                reason_text="custom substrate gap text",
            ),
        )


def test_engine_records_substrate_gap_on_run_aggregate() -> None:
    run_repo = FakeOptimizationRunRepository()
    audit = RecordingAuditPort()
    result = asyncio.run(
        run_optimization(
            tenant_context=_tenant_ctx(),
            invoked_by_user_id="cli-operator",
            rules=(_SubstrateGapRule(),),
            evidence_context=_empty_evidence_context(),
            optimization_run_repository=run_repo,
            recommendation_repository=FakeRecommendationRepository(),
            audit_port=audit,
            now=_NOW,
        )
    )
    assert result.run.status is OptimizationRunStatus.COMPLETED
    assert result.skipped_categories["model_choice"].reason_code == "custom_gap"
    stored = list(run_repo.runs.values())[0]
    assert (
        stored.skipped_categories["model_choice"].reason_code == "custom_gap"
    )


# ----------------------------------------------------------------------
# Tenant isolation
# ----------------------------------------------------------------------


def test_engine_isolates_persisted_run_by_tenant() -> None:
    run_repo = FakeOptimizationRunRepository()
    asyncio.run(
        run_optimization(
            tenant_context=_tenant_ctx(_TENANT_A),
            invoked_by_user_id="cli-operator",
            rules=default_rules(),
            evidence_context=_empty_evidence_context(_tenant_ctx(_TENANT_A)),
            optimization_run_repository=run_repo,
            recommendation_repository=FakeRecommendationRepository(),
            audit_port=RecordingAuditPort(),
            now=_NOW,
        )
    )
    asyncio.run(
        run_optimization(
            tenant_context=_tenant_ctx(_TENANT_B),
            invoked_by_user_id="cli-operator",
            rules=default_rules(),
            evidence_context=_empty_evidence_context(_tenant_ctx(_TENANT_B)),
            optimization_run_repository=run_repo,
            recommendation_repository=FakeRecommendationRepository(),
            audit_port=RecordingAuditPort(),
            now=_NOW,
        )
    )
    a_runs = [
        r
        for r in run_repo.runs.values()
        if str(r.tenant_id) == _TENANT_A
    ]
    b_runs = [
        r
        for r in run_repo.runs.values()
        if str(r.tenant_id) == _TENANT_B
    ]
    assert len(a_runs) == 1
    assert len(b_runs) == 1
