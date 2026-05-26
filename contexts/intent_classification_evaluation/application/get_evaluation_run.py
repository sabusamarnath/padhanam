"""Get-evaluation-run use case (D137, S48b)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from contexts.intent_classification_evaluation.domain.evaluation_result import (
    EvaluationAggregate,
    EvaluationResult,
)
from contexts.intent_classification_evaluation.domain.evaluation_run import (
    EvaluationRun,
)
from contexts.intent_classification_evaluation.ports.reader import (
    EvaluationRunReader,
)
from shared_kernel import TenantContext


@dataclass(frozen=True)
class EvaluationRunDetail:
    """A run plus its per-entry results and per-class aggregates."""

    run: EvaluationRun
    results: tuple[EvaluationResult, ...]
    aggregates: tuple[EvaluationAggregate, ...]


async def get_evaluation_run(
    run_id: UUID,
    *,
    reader: EvaluationRunReader,
    tenant: TenantContext,
) -> EvaluationRunDetail | None:
    """Return the run plus its per-entry results and per-class aggregates."""
    run = await reader.get_run(run_id, tenant=tenant)
    if run is None:
        return None
    results = await reader.list_results(run_id, tenant=tenant)
    aggregates = await reader.list_aggregates(run_id, tenant=tenant)
    return EvaluationRunDetail(
        run=run, results=results, aggregates=aggregates
    )


__all__ = ["EvaluationRunDetail", "get_evaluation_run"]
