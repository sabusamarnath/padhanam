"""List-evaluation-runs use case (D137, S48b)."""

from __future__ import annotations

from contexts.intent_classification_evaluation.domain.evaluation_run import (
    EvaluationRun,
)
from contexts.intent_classification_evaluation.ports.reader import (
    EvaluationRunReader,
)
from shared_kernel import TenantContext


async def list_evaluation_runs(
    *,
    reader: EvaluationRunReader,
    tenant: TenantContext,
    limit: int = 20,
) -> tuple[EvaluationRun, ...]:
    """List recent evaluation runs in this tenant, newest first."""
    return await reader.list_runs(tenant=tenant, limit=limit)


__all__ = ["list_evaluation_runs"]
