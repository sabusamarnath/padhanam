"""run_retrieval_evaluation use case (D110 commitments 5, 6, 7; D111 cmt 6).

The orchestrator the runner CLI subcommand invokes. Reads the
gold-set revision the operator named, exercises every entry against
every executing D66-registered strategy via the consumer-defined
``RetrievalRunnerPort``, computes per-query metrics on the fly via
the injected ``MetricCalculator``, persists per-query records,
computes per-strategy aggregates at run-completion time via the same
calculator, persists aggregates, and transitions the run to
``completed`` (or to ``failed`` on any uncaught exception).

Every write to the three runner tables emits an audit event via
``AuditPort`` per D110 commitment 7. The audit context's existing
chain integrity transitively guarantees tamper-evidence on the
runner records (the platform-computed-records regime named in
commitment 7's reasoning).

Per D110 commitment 6 the strategy set is sourced from
``application/strategy_keys.EXECUTING_STRATEGIES`` (currently
``vector_only`` and ``graph_only``; ``parallel_rrf`` deferred per
``charter/deferred-decisions.md``).

Per D111 commitment 6 the metric primitives sit behind the
``MetricCalculator`` Protocol with ``BinaryRelevanceMetrics`` as
the default implementation. Composition roots inject the calculator
so Phase 2 graded-relevance implementations (nDCG, MAP per D105
deferred alternatives) land as siblings without runner change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from contexts.audit.domain.ports import AuditPort

from shared_kernel.tenant_context import TenantContext

from contexts.retrieval_evaluation.application.append_entry_to_revision import (
    GoldSetNotFoundError,
)
from contexts.retrieval_evaluation.application.audit_events import (
    draft_aggregate_append,
    draft_result_append,
    draft_run_start,
    draft_run_terminal,
)
from contexts.retrieval_evaluation.application.strategy_keys import (
    EXECUTING_STRATEGIES,
    to_adapter_dispatch,
)
from contexts.retrieval_evaluation.domain import (
    EvaluationAggregate,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunStatus,
    GoldSetEntry,
    MetricCalculator,
    PerQueryMetrics,
)
from contexts.retrieval_evaluation.ports.evaluation_run_repository import (
    EvaluationRunRepository,
)
from contexts.retrieval_evaluation.ports.reader import GoldSetReader
from contexts.retrieval_evaluation.ports.retrieval_runner import (
    RetrievalRunnerPort,
)


class GoldSetMissingFinalizedRevisionError(Exception):
    """Raised when the named gold set has no finalized current revision."""


# Evaluation runs cap retrieval at the highest supported k value plus
# a small headroom for ranking-tail observations. k=10 is the largest
# in SUPPORTED_K_VALUES per D110 commitment 3; the runner asks the
# adapter for 10 results so metrics at every k are meaningful.
RUNNER_TOP_K: int = 10


@dataclass(frozen=True)
class RunRetrievalEvaluationResult:
    """Aggregate result returned at orchestration completion."""

    run: EvaluationRun
    results: tuple[EvaluationResult, ...]
    aggregates: tuple[EvaluationAggregate, ...]


async def run_retrieval_evaluation(
    *,
    tenant_context: TenantContext,
    gold_set_id: UUID,
    invoked_by_user_id: str,
    reader: GoldSetReader,
    repository: EvaluationRunRepository,
    retrieval_runner: RetrievalRunnerPort,
    audit_port: AuditPort,
    metric_calculator: MetricCalculator,
    now: datetime | None = None,
    run_id: UUID | None = None,
) -> RunRetrievalEvaluationResult:
    """Orchestrate one EvaluationRun against the gold set's current revision."""
    invoked_at = now or datetime.now(timezone.utc)
    run_uuid = run_id or uuid4()

    snapshot = await reader.get_gold_set_with_current_revision(
        tenant_context=tenant_context,
        gold_set_id=gold_set_id,
    )
    if snapshot is None:
        raise GoldSetNotFoundError(
            f"gold set {gold_set_id} not found for tenant "
            f"{tenant_context.tenant_id}"
        )
    if snapshot.current_revision is None or not snapshot.entries:
        raise GoldSetMissingFinalizedRevisionError(
            f"gold set {gold_set_id} has no finalized revision with entries"
        )

    run = EvaluationRun(
        id=run_uuid,
        tenant_id=UUID(tenant_context.tenant_id),
        jurisdiction=tenant_context.jurisdiction,
        gold_set_id=gold_set_id,
        gold_set_revision_id=snapshot.current_revision.id,
        invoked_by_user_id=invoked_by_user_id,
        invoked_at=invoked_at,
        completed_at=None,
        status=EvaluationRunStatus.RUNNING,
    )
    await repository.persist_run(tenant_context=tenant_context, run=run)
    await audit_port.emit(
        draft_run_start(tenant_context=tenant_context, run=run)
    )

    try:
        per_query_results: list[EvaluationResult] = []
        per_strategy_metrics: dict[str, list[PerQueryMetrics]] = {
            s: [] for s in EXECUTING_STRATEGIES
        }
        per_strategy_latency: dict[str, list[int]] = {
            s: [] for s in EXECUTING_STRATEGIES
        }

        for entry in snapshot.entries:
            for strategy in EXECUTING_STRATEGIES:
                result, per_query_metrics = await _exercise_entry_against_strategy(
                    entry=entry,
                    strategy=strategy,
                    tenant_context=tenant_context,
                    run_id=run.id,
                    retrieval_runner=retrieval_runner,
                    metric_calculator=metric_calculator,
                )
                await repository.persist_result(
                    tenant_context=tenant_context, result=result
                )
                await audit_port.emit(
                    draft_result_append(
                        tenant_context=tenant_context,
                        run=run,
                        result=result,
                    )
                )
                per_query_results.append(result)
                per_strategy_metrics[strategy].append(per_query_metrics)
                per_strategy_latency[strategy].append(result.latency_ms)

        aggregates: list[EvaluationAggregate] = []
        for strategy in EXECUTING_STRATEGIES:
            aggregated = metric_calculator.aggregate_per_strategy(
                per_query_results=per_strategy_metrics[strategy],
                latencies_ms=per_strategy_latency[strategy],
            )
            aggregate = EvaluationAggregate(
                id=uuid4(),
                evaluation_run_id=run.id,
                retrieval_strategy=strategy,
                recall_at_k_mean=aggregated.recall_at_k_mean,
                precision_at_k_mean=aggregated.precision_at_k_mean,
                mrr_mean=aggregated.mrr_mean,
                latency_ms_p50=aggregated.latency_ms_p50,
                latency_ms_p95=aggregated.latency_ms_p95,
                latency_ms_mean=aggregated.latency_ms_mean,
            )
            await repository.persist_aggregate(
                tenant_context=tenant_context, aggregate=aggregate
            )
            await audit_port.emit(
                draft_aggregate_append(
                    tenant_context=tenant_context,
                    run=run,
                    aggregate=aggregate,
                )
            )
            aggregates.append(aggregate)

        completed_at = datetime.now(timezone.utc)
        await repository.mark_completed(
            tenant_context=tenant_context,
            run_id=run.id,
            completed_at=completed_at,
        )
        completed_run = EvaluationRun(
            id=run.id,
            tenant_id=run.tenant_id,
            jurisdiction=run.jurisdiction,
            gold_set_id=run.gold_set_id,
            gold_set_revision_id=run.gold_set_revision_id,
            invoked_by_user_id=run.invoked_by_user_id,
            invoked_at=run.invoked_at,
            completed_at=completed_at,
            status=EvaluationRunStatus.COMPLETED,
        )
        await audit_port.emit(
            draft_run_terminal(
                tenant_context=tenant_context,
                run=completed_run,
                completed_at=completed_at,
                new_status="completed",
            )
        )
        return RunRetrievalEvaluationResult(
            run=completed_run,
            results=tuple(per_query_results),
            aggregates=tuple(aggregates),
        )
    except Exception:
        failed_at = datetime.now(timezone.utc)
        await repository.mark_failed(
            tenant_context=tenant_context,
            run_id=run.id,
            completed_at=failed_at,
        )
        failed_run = EvaluationRun(
            id=run.id,
            tenant_id=run.tenant_id,
            jurisdiction=run.jurisdiction,
            gold_set_id=run.gold_set_id,
            gold_set_revision_id=run.gold_set_revision_id,
            invoked_by_user_id=run.invoked_by_user_id,
            invoked_at=run.invoked_at,
            completed_at=failed_at,
            status=EvaluationRunStatus.FAILED,
        )
        await audit_port.emit(
            draft_run_terminal(
                tenant_context=tenant_context,
                run=failed_run,
                completed_at=failed_at,
                new_status="failed",
            )
        )
        raise


async def _exercise_entry_against_strategy(
    *,
    entry: GoldSetEntry,
    strategy: str,
    tenant_context: TenantContext,
    run_id: UUID,
    retrieval_runner: RetrievalRunnerPort,
    metric_calculator: MetricCalculator,
) -> tuple[EvaluationResult, PerQueryMetrics]:
    dispatch = to_adapter_dispatch(strategy)
    ranked = await retrieval_runner(
        query=entry.query,
        tenant_context=tenant_context,
        strategy_dispatch=dispatch,
        top_k=RUNNER_TOP_K,
    )
    per_query = metric_calculator.compute_per_query(
        returned=ranked.chunk_ids,
        expected=entry.expected_chunk_ids,
    )
    result = EvaluationResult(
        id=uuid4(),
        evaluation_run_id=run_id,
        gold_set_entry_id=entry.id,
        retrieval_strategy=strategy,
        returned_chunk_ids=ranked.chunk_ids,
        recall_at_k=per_query.recall_at_k,
        precision_at_k=per_query.precision_at_k,
        mrr=per_query.mrr,
        latency_ms=ranked.latency_ms,
    )
    return result, per_query


__all__ = [
    "GoldSetMissingFinalizedRevisionError",
    "RUNNER_TOP_K",
    "RunRetrievalEvaluationResult",
    "run_retrieval_evaluation",
]
