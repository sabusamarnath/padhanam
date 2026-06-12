"""Unit tests for the four default RecommendationRule implementations.

Coverage:

- RetrievalStrategyRule: triggers on recall@3 delta above threshold,
  suppresses below, populates all-k deltas in citation, attaches
  CaveatAnnotation for all-zero aggregates, handles single-strategy
  runs without emission, respects tenant scoping.
- CostOptimizationRule: aggregates by agent_template_id over a
  bounded window, triggers above threshold, suppresses below,
  surfaces successful-vs-total ratio in citation, respects window.
- ModelChoiceRule: raises SubstrateGapError with structured reason.
- PromptRevisionRule: raises SubstrateGapError with structured reason.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from contexts.optimization.application.evidence_context import EvidenceContext
from contexts.optimization.application.rules import (
    CostOptimizationRule,
    ModelChoiceRule,
    PromptRevisionRule,
    RetrievalStrategyRule,
)
from contexts.optimization.domain import (
    CAVEAT_INFRASTRUCTURE_SUBSTRATE_CHECK_REQUIRED,
    RecommendationCandidate,
    RecommendationCategory,
    SubstrateGapError,
)
from contexts.retrieval_evaluation.domain import (
    EvaluationAggregate,
    EvaluationRun,
    EvaluationRunStatus,
)
from contexts.run_history.domain.run_record import RunRecord
from shared_kernel.tenant_context import TenantContext
from tests.unit.contexts.optimization.application._fakes import (
    FakeAuditEventReader,
    FakeEvaluationRunReader,
    FakeGoldSetReader,
    FakeRunHistoryReader,
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


def _context(
    *,
    tenant: TenantContext | None = None,
    evaluation_run_reader: FakeEvaluationRunReader | None = None,
    run_history_reader: FakeRunHistoryReader | None = None,
) -> EvidenceContext:
    return EvidenceContext(
        tenant_context=tenant or _tenant_ctx(),
        evaluation_run_reader=evaluation_run_reader or FakeEvaluationRunReader(),
        run_history_reader=run_history_reader or FakeRunHistoryReader(),
        gold_set_reader=FakeGoldSetReader(),
        audit_event_reader=FakeAuditEventReader(),
    )


def _run(
    *,
    tenant_id: str = _TENANT_A,
    run_id: UUID | None = None,
    gold_set_id: UUID | None = None,
) -> EvaluationRun:
    return EvaluationRun(
        id=run_id or uuid4(),
        tenant_id=UUID(tenant_id),
        jurisdiction="GB",
        gold_set_id=gold_set_id or uuid4(),
        gold_set_revision_id=uuid4(),
        invoked_by_user_id="cli-operator",
        invoked_at=_NOW,
        completed_at=_NOW,
        status=EvaluationRunStatus.COMPLETED,
    )


def _aggregate(
    *,
    run_id: UUID,
    strategy: str,
    recall_at_3: float,
    precision_at_3: float = 0.5,
    mrr: Decimal = Decimal("1.0000"),
) -> EvaluationAggregate:
    return EvaluationAggregate(
        id=uuid4(),
        evaluation_run_id=run_id,
        retrieval_strategy=strategy,
        recall_at_k_mean={
            1: recall_at_3 * 0.5,
            3: recall_at_3,
            5: min(1.0, recall_at_3 * 1.1),
            10: min(1.0, recall_at_3 * 1.2),
        },
        precision_at_k_mean={
            1: precision_at_3,
            3: precision_at_3,
            5: precision_at_3,
            10: precision_at_3,
        },
        mrr_mean=mrr,
        latency_ms_p50=100,
        latency_ms_p95=200,
        latency_ms_mean=120,
    )


def _all_zero_aggregate(
    *,
    run_id: UUID,
    strategy: str,
) -> EvaluationAggregate:
    return EvaluationAggregate(
        id=uuid4(),
        evaluation_run_id=run_id,
        retrieval_strategy=strategy,
        recall_at_k_mean={1: 0.0, 3: 0.0, 5: 0.0, 10: 0.0},
        precision_at_k_mean={1: 0.0, 3: 0.0, 5: 0.0, 10: 0.0},
        mrr_mean=Decimal("0.0000"),
        latency_ms_p50=0,
        latency_ms_p95=0,
        latency_ms_mean=0,
    )


def _run_record(
    *,
    tenant_id: str = _TENANT_A,
    template_id: UUID | None = None,
    cost: Decimal = Decimal("0.01"),
    started_at: datetime | None = None,
    termination_reason: str = "content",
    iteration_count: int = 1,
) -> RunRecord:
    template = template_id or uuid4()
    return RunRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        jurisdiction="GB",
        agent_template_id=template,
        agent_template_version=1,
        input_message="hello",
        output_content="ok",
        started_at=started_at or _NOW,
        completed_at=(started_at or _NOW) + timedelta(seconds=1),
        termination_reason=termination_reason,
        iteration_count=iteration_count,
        total_cost_usd=cost,
        trace_id=None,
        audit_start_hash="a" * 64,
        audit_end_hash="b" * 64 if termination_reason != "failed" else None,
        created_at=_NOW,
    )


# ----------------------------------------------------------------------
# RetrievalStrategyRule
# ----------------------------------------------------------------------


def test_retrieval_strategy_rule_triggers_above_threshold() -> None:
    run_id, gold_set_id = uuid4(), uuid4()
    run = _run(run_id=run_id, gold_set_id=gold_set_id)
    reader = FakeEvaluationRunReader(
        runs=[run],
        aggregates={
            run_id: (
                _aggregate(run_id=run_id, strategy="graph_only", recall_at_3=0.0),
                _aggregate(run_id=run_id, strategy="vector_only", recall_at_3=0.8),
            ),
        },
    )
    rule = RetrievalStrategyRule()
    candidates = asyncio.run(
        rule.evaluate(evidence_context=_context(evaluation_run_reader=reader))
    )
    candidates = list(candidates)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.category is RecommendationCategory.RETRIEVAL_STRATEGY
    assert "graph_only" in candidate.text
    assert "vector_only" in candidate.text
    citation = candidate.evidence_citations[0]
    assert citation.evaluation_run_id == run_id
    assert citation.gold_set_id == gold_set_id
    assert set(citation.comparison.recall_at_k_delta.keys()) == {1, 3, 5, 10}


def test_retrieval_strategy_rule_suppresses_below_threshold() -> None:
    run_id = uuid4()
    run = _run(run_id=run_id)
    reader = FakeEvaluationRunReader(
        runs=[run],
        aggregates={
            run_id: (
                _aggregate(run_id=run_id, strategy="a", recall_at_3=0.50),
                _aggregate(run_id=run_id, strategy="b", recall_at_3=0.55),
            ),
        },
    )
    rule = RetrievalStrategyRule(recall_at_k_delta_threshold=0.15)
    candidates = list(asyncio.run(
        rule.evaluate(evidence_context=_context(evaluation_run_reader=reader))
    ))
    assert candidates == []


def test_retrieval_strategy_rule_attaches_caveat_for_all_zero_strategy() -> None:
    run_id = uuid4()
    run = _run(run_id=run_id)
    reader = FakeEvaluationRunReader(
        runs=[run],
        aggregates={
            run_id: (
                _all_zero_aggregate(run_id=run_id, strategy="graph_only"),
                _aggregate(run_id=run_id, strategy="vector_only", recall_at_3=0.8),
            ),
        },
    )
    rule = RetrievalStrategyRule()
    candidates = list(asyncio.run(
        rule.evaluate(evidence_context=_context(evaluation_run_reader=reader))
    ))
    assert len(candidates) == 1
    citation = candidates[0].evidence_citations[0]
    assert len(citation.caveats) == 1
    caveat = citation.caveats[0]
    assert caveat.strategy_id == "graph_only"
    assert caveat.state == "all_zero_aggregates"
    assert caveat.caveat_code == CAVEAT_INFRASTRUCTURE_SUBSTRATE_CHECK_REQUIRED


def test_retrieval_strategy_rule_skips_single_strategy_runs() -> None:
    run_id = uuid4()
    run = _run(run_id=run_id)
    reader = FakeEvaluationRunReader(
        runs=[run],
        aggregates={
            run_id: (_aggregate(run_id=run_id, strategy="solo", recall_at_3=0.5),),
        },
    )
    rule = RetrievalStrategyRule()
    candidates = list(asyncio.run(
        rule.evaluate(evidence_context=_context(evaluation_run_reader=reader))
    ))
    assert candidates == []


def test_retrieval_strategy_rule_ignores_other_tenants() -> None:
    run_id = uuid4()
    other_run = _run(tenant_id=_TENANT_B, run_id=run_id)
    reader = FakeEvaluationRunReader(
        runs=[other_run],
        aggregates={
            run_id: (
                _aggregate(run_id=run_id, strategy="a", recall_at_3=0.0),
                _aggregate(run_id=run_id, strategy="b", recall_at_3=1.0),
            ),
        },
    )
    rule = RetrievalStrategyRule()
    candidates = list(asyncio.run(
        rule.evaluate(
            evidence_context=_context(
                tenant=_tenant_ctx(_TENANT_A),
                evaluation_run_reader=reader,
            )
        )
    ))
    assert candidates == []


def test_retrieval_strategy_rule_ignores_non_completed_runs() -> None:
    run_id = uuid4()
    running = EvaluationRun(
        id=run_id,
        tenant_id=UUID(_TENANT_A),
        jurisdiction="GB",
        gold_set_id=uuid4(),
        gold_set_revision_id=uuid4(),
        invoked_by_user_id="cli-operator",
        invoked_at=_NOW,
        completed_at=None,
        status=EvaluationRunStatus.RUNNING,
    )
    reader = FakeEvaluationRunReader(runs=[running])
    rule = RetrievalStrategyRule()
    candidates = list(asyncio.run(
        rule.evaluate(evidence_context=_context(evaluation_run_reader=reader))
    ))
    assert candidates == []


# ----------------------------------------------------------------------
# CostOptimizationRule
# ----------------------------------------------------------------------


def test_cost_optimization_rule_triggers_above_threshold() -> None:
    template_id = uuid4()
    runs = [
        _run_record(template_id=template_id, cost=Decimal("0.20")),
        _run_record(template_id=template_id, cost=Decimal("0.20")),
    ]
    reader = FakeRunHistoryReader(records=runs)
    rule = CostOptimizationRule(
        cost_per_successful_task_threshold_usd=0.10,
        window_days=14,
        now=_NOW + timedelta(days=1),
    )
    candidates = list(asyncio.run(
        rule.evaluate(evidence_context=_context(run_history_reader=reader))
    ))
    assert len(candidates) == 1
    citation = candidates[0].evidence_citations[0]
    assert citation.cost_aggregate.agent_template_id == template_id
    assert citation.cost_aggregate.n_successful_runs == 2
    assert citation.cost_aggregate.mean_cost_per_successful_task_usd == Decimal(
        "0.20"
    )


def test_cost_optimization_rule_suppresses_below_threshold() -> None:
    template_id = uuid4()
    runs = [
        _run_record(template_id=template_id, cost=Decimal("0.05")),
        _run_record(template_id=template_id, cost=Decimal("0.05")),
    ]
    reader = FakeRunHistoryReader(records=runs)
    rule = CostOptimizationRule(
        cost_per_successful_task_threshold_usd=0.10,
        now=_NOW + timedelta(days=1),
    )
    candidates = list(asyncio.run(
        rule.evaluate(evidence_context=_context(run_history_reader=reader))
    ))
    assert candidates == []


def test_cost_optimization_rule_excludes_unsuccessful_terminations() -> None:
    template_id = uuid4()
    runs = [
        _run_record(
            template_id=template_id,
            cost=Decimal("1.00"),
            termination_reason="error",
        ),
    ]
    reader = FakeRunHistoryReader(records=runs)
    rule = CostOptimizationRule(
        cost_per_successful_task_threshold_usd=0.10,
        now=_NOW + timedelta(days=1),
    )
    candidates = list(asyncio.run(
        rule.evaluate(evidence_context=_context(run_history_reader=reader))
    ))
    assert candidates == []


def test_cost_optimization_rule_reports_total_runs_in_citation() -> None:
    template_id = uuid4()
    runs = [
        _run_record(template_id=template_id, cost=Decimal("0.20")),
        _run_record(
            template_id=template_id,
            cost=Decimal("0.20"),
            termination_reason="error",
        ),
    ]
    reader = FakeRunHistoryReader(records=runs)
    rule = CostOptimizationRule(
        cost_per_successful_task_threshold_usd=0.10,
        now=_NOW + timedelta(days=1),
    )
    candidates = list(asyncio.run(
        rule.evaluate(evidence_context=_context(run_history_reader=reader))
    ))
    assert len(candidates) == 1
    aggregate = candidates[0].evidence_citations[0].cost_aggregate
    assert aggregate.n_successful_runs == 1
    assert aggregate.n_runs_total == 2


def test_cost_optimization_rule_excludes_runs_outside_window() -> None:
    template_id = uuid4()
    inside_window = _NOW
    outside_window = _NOW - timedelta(days=20)
    runs = [
        _run_record(
            template_id=template_id,
            cost=Decimal("0.20"),
            started_at=outside_window,
        ),
    ]
    reader = FakeRunHistoryReader(records=runs)
    rule = CostOptimizationRule(
        cost_per_successful_task_threshold_usd=0.10,
        window_days=14,
        now=inside_window + timedelta(seconds=1),
    )
    candidates = list(asyncio.run(
        rule.evaluate(evidence_context=_context(run_history_reader=reader))
    ))
    assert candidates == []


def test_cost_optimization_rule_ignores_other_tenants() -> None:
    template_id = uuid4()
    runs = [
        _run_record(
            tenant_id=_TENANT_B,
            template_id=template_id,
            cost=Decimal("1.00"),
        ),
    ]
    reader = FakeRunHistoryReader(records=runs)
    rule = CostOptimizationRule(
        cost_per_successful_task_threshold_usd=0.10,
        now=_NOW + timedelta(days=1),
    )
    candidates = list(asyncio.run(
        rule.evaluate(
            evidence_context=_context(
                tenant=_tenant_ctx(_TENANT_A),
                run_history_reader=reader,
            )
        )
    ))
    assert candidates == []


# ----------------------------------------------------------------------
# Phase 1 zero rules
# ----------------------------------------------------------------------


def test_model_choice_rule_raises_substrate_gap_error() -> None:
    rule = ModelChoiceRule()
    with pytest.raises(SubstrateGapError) as excinfo:
        asyncio.run(rule.evaluate(evidence_context=_context()))
    assert excinfo.value.category is RecommendationCategory.MODEL_CHOICE
    assert excinfo.value.reason.reason_code == "substrate_gap"
    assert "scoring-sheet" in excinfo.value.reason.reason_text


def test_prompt_revision_rule_raises_substrate_gap_error() -> None:
    rule = PromptRevisionRule()
    with pytest.raises(SubstrateGapError) as excinfo:
        asyncio.run(rule.evaluate(evidence_context=_context()))
    assert excinfo.value.category is RecommendationCategory.PROMPT_REVISION
    assert excinfo.value.reason.reason_code == "substrate_gap"
    assert "criterion-failure" in excinfo.value.reason.reason_text


# ----------------------------------------------------------------------
# default_rules helper
# ----------------------------------------------------------------------


def test_default_rules_returns_five_in_order() -> None:
    from contexts.optimization.application.rules import default_rules

    rules = default_rules()
    # Four inference rules + the first non-inference rule (matcher suppression,
    # D185/S91), registered last.
    assert len(rules) == 5
    categories = [r.category for r in rules]
    assert categories == [
        RecommendationCategory.RETRIEVAL_STRATEGY,
        RecommendationCategory.COST_OPTIMIZATION,
        RecommendationCategory.MODEL_CHOICE,
        RecommendationCategory.PROMPT_REVISION,
        RecommendationCategory.MATCHER_SUPPRESSION,
    ]
