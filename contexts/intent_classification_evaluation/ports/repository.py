"""EvaluationRunRepository port for intent-classification evaluation (D137).

Write-side port persisting EvaluationRun aggregates, EvaluationResult
records, and EvaluationAggregate records. Per D110's audit-event-
level tamper-evidence, the repository emits audit events on each
write inside the same transaction.

Domain-layer Protocol — adapters at
``contexts.intent_classification_evaluation.adapters.outbound.postgres``
implement against Postgres with bound-tenant defence-in-depth.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from contexts.intent_classification_evaluation.domain.evaluation_result import (
    EvaluationAggregate,
    EvaluationResult,
)
from contexts.intent_classification_evaluation.domain.evaluation_run import (
    EvaluationRun,
)
from shared_kernel import TenantContext


@runtime_checkable
class EvaluationRunRepository(Protocol):
    """Persistence port for intent-classification evaluation."""

    async def create_run(
        self, run: EvaluationRun, *, tenant: TenantContext
    ) -> None:
        """Persist a new EvaluationRun in running status."""
        ...

    async def update_run(
        self, run: EvaluationRun, *, tenant: TenantContext
    ) -> None:
        """Persist a status transition (running -> completed or failed)."""
        ...

    async def append_result(
        self, result: EvaluationResult, *, tenant: TenantContext
    ) -> None:
        """Persist one per-entry EvaluationResult."""
        ...

    async def write_aggregates(
        self,
        aggregates: tuple[EvaluationAggregate, ...],
        *,
        tenant: TenantContext,
    ) -> None:
        """Persist the per-class EvaluationAggregate records for a run."""
        ...


__all__ = ["EvaluationRunRepository"]
