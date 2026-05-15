"""get_evaluation_run use case (D110 commitment 2-4 read surface)."""

from __future__ import annotations

from uuid import UUID

from shared_kernel.tenant_context import TenantContext

from contexts.retrieval_evaluation.ports.evaluation_run_reader import (
    EvaluationRunReader,
    EvaluationRunSnapshot,
)


async def get_evaluation_run(
    *,
    tenant_context: TenantContext,
    run_id: UUID,
    reader: EvaluationRunReader,
) -> EvaluationRunSnapshot | None:
    """Return the run plus per-query results plus per-strategy aggregates.

    Returns None on cross-tenant access or when the run does not exist.
    """
    return await reader.get_run_with_results_and_aggregates(
        tenant_context=tenant_context,
        run_id=run_id,
    )


__all__ = ["get_evaluation_run"]
