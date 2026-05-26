"""EvaluationRunReader consumer port for intent-classification evaluation (D137).

Read-side port returning EvaluationRun aggregates plus their
EvaluationResult and EvaluationAggregate records. Consumer-defined
in the sense that the application's use cases shape this port; the
adapter implements against Postgres.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from contexts.intent_classification_evaluation.domain.evaluation_result import (
    EvaluationAggregate,
    EvaluationResult,
)
from contexts.intent_classification_evaluation.domain.evaluation_run import (
    EvaluationRun,
)
from shared_kernel import TenantContext


@runtime_checkable
class EvaluationRunReader(Protocol):
    """Read-side port for intent-classification evaluation runs."""

    async def get_run(
        self, run_id: UUID, *, tenant: TenantContext
    ) -> EvaluationRun | None:
        """Return the run by id, or None if not found in this tenant."""
        ...

    async def list_runs(
        self,
        *,
        tenant: TenantContext,
        limit: int = 20,
    ) -> tuple[EvaluationRun, ...]:
        """Return recent runs in this tenant, newest first."""
        ...

    async def list_results(
        self, run_id: UUID, *, tenant: TenantContext
    ) -> tuple[EvaluationResult, ...]:
        """Return per-entry results for a run, ordered by entry_index."""
        ...

    async def list_aggregates(
        self, run_id: UUID, *, tenant: TenantContext
    ) -> tuple[EvaluationAggregate, ...]:
        """Return per-class aggregates for a run."""
        ...


__all__ = ["EvaluationRunReader"]
