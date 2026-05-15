"""run_retrieval_evaluation use case (D110 commitments 5, 6, 7).

The orchestrator the runner CLI subcommand invokes. Reads the
gold-set revision the operator named, exercises every entry against
every executing D66-registered strategy via the consumer-defined
``RetrievalRunnerPort``, computes per-query metrics on the fly,
persists per-query records, computes per-strategy aggregates at
run-completion time, persists aggregates, and transitions the run
to ``completed`` (or to ``failed`` on any uncaught exception).

Every write to the three runner tables emits an audit event via
``AuditPort`` per D110 commitment 7. The audit context's existing
chain integrity transitively guarantees tamper-evidence on the
runner records (the platform-computed-records regime named in
commitment 7's reasoning).

Per D110 commitment 6 the strategy set is sourced from
``application/strategy_keys.EXECUTING_STRATEGIES`` (currently
``vector_only`` and ``graph_only``; ``parallel_rrf`` deferred per
``charter/deferred-decisions.md``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Mapping
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
)
from contexts.retrieval_evaluation.domain.metrics import (
    compute_per_k_metrics,
    latency_percentiles,
    mean_mrr,
    mean_per_k,
    mean_reciprocal_rank,
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
        per_strategy_recall: dict[str, list[Mapping[int, float]]] = {
            s: [] for s in EXECUTING_STRATEGIES
        }
        per_strategy_precision: dict[str, list[Mapping[int, float]]] = {
            s: [] for s in EXECUTING_STRATEGIES
        }
        per_strategy_mrr: dict[str, list[Decimal]] = {
            s: [] for s in EXECUTING_STRATEGIES
        }
        per_strategy_latency: dict[str, list[int]] = {
            s: [] for s in EXECUTING_STRATEGIES
        }

        for entry in snapshot.entries:
            for strategy in EXECUTING_STRATEGIES:
                result = await _exercise_entry_against_strategy(
                    entry=entry,
                    strategy=strategy,
                    tenant_context=tenant_context,
                    run_id=run.id,
                    retrieval_runner=retrieval_runner,
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
                per_strategy_recall[strategy].append(result.recall_at_k)
                per_strategy_precision[strategy].append(result.precision_at_k)
                per_strategy_mrr[strategy].append(result.mrr)
                per_strategy_latency[strategy].append(result.latency_ms)

        aggregates: list[EvaluationAggregate] = []
        for strategy in EXECUTING_STRATEGIES:
            p50, p95, mean_latency = latency_percentiles(
                per_strategy_latency[strategy]
            )
            aggregate = EvaluationAggregate(
                id=uuid4(),
                evaluation_run_id=run.id,
                retrieval_strategy=strategy,
                recall_at_k_mean=mean_per_k(per_strategy_recall[strategy]),
                precision_at_k_mean=mean_per_k(
                    per_strategy_precision[strategy]
                ),
                mrr_mean=mean_mrr(per_strategy_mrr[strategy]),
                latency_ms_p50=p50,
                latency_ms_p95=p95,
                latency_ms_mean=mean_latency,
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
) -> EvaluationResult:
    dispatch = to_adapter_dispatch(strategy)
    ranked = await retrieval_runner(
        query=entry.query,
        tenant_context=tenant_context,
        strategy_dispatch=dispatch,
        top_k=RUNNER_TOP_K,
    )
    recall, precision = compute_per_k_metrics(
        returned=ranked.chunk_ids,
        expected=entry.expected_chunk_ids,
    )
    mrr = mean_reciprocal_rank(
        returned=ranked.chunk_ids,
        expected=entry.expected_chunk_ids,
    )
    return EvaluationResult(
        id=uuid4(),
        evaluation_run_id=run_id,
        gold_set_entry_id=entry.id,
        retrieval_strategy=strategy,
        returned_chunk_ids=ranked.chunk_ids,
        recall_at_k=recall,
        precision_at_k=precision,
        mrr=mrr,
        latency_ms=ranked.latency_ms,
    )


__all__ = [
    "GoldSetMissingFinalizedRevisionError",
    "RUNNER_TOP_K",
    "RunRetrievalEvaluationResult",
    "run_retrieval_evaluation",
]
