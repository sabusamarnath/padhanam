"""Write-side port for the retrieval-evaluation runner (D110).

The runner orchestrator invokes this port to persist three record
types and to transition the parent aggregate's status lifecycle:

- ``persist_run`` — insert the ``EvaluationRun`` aggregate root with
  ``status='running'`` at orchestration begin.
- ``persist_result`` — insert one per-query-per-strategy
  ``EvaluationResult`` row. Append-only per D110 commitment 3.
- ``persist_aggregate`` — insert one per-strategy ``EvaluationAggregate``
  row computed at run-completion time per D110 commitment 4.
- ``mark_completed`` — transition the aggregate to terminal
  ``status='completed'`` with ``completed_at`` populated.
- ``mark_failed`` — transition to terminal ``status='failed'``.

The port stays consumer-defined per D17: the use cases speak the
domain shape (``EvaluationRun``, ``EvaluationResult``,
``EvaluationAggregate``); the adapter translates to and from the
Postgres row shape.

Ports layer is pure per D16 — no SQLAlchemy, no asyncpg.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from shared_kernel.tenant_context import TenantContext

from contexts.retrieval_evaluation.domain import (
    EvaluationAggregate,
    EvaluationResult,
    EvaluationRun,
)


class EvaluationRunRepository(Protocol):
    """Write-side port for the retrieval-evaluation runner."""

    async def persist_run(
        self,
        *,
        tenant_context: TenantContext,
        run: EvaluationRun,
    ) -> None:
        """Insert the run aggregate at orchestration begin (status='running')."""
        ...

    async def persist_result(
        self,
        *,
        tenant_context: TenantContext,
        result: EvaluationResult,
    ) -> None:
        """Append one per-query-per-strategy result row."""
        ...

    async def persist_aggregate(
        self,
        *,
        tenant_context: TenantContext,
        aggregate: EvaluationAggregate,
    ) -> None:
        """Append one per-strategy aggregate row at run-completion time."""
        ...

    async def mark_completed(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
        completed_at: datetime,
    ) -> None:
        """Transition status='running' → 'completed' and set completed_at."""
        ...

    async def mark_failed(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
        completed_at: datetime,
    ) -> None:
        """Transition status='running' → 'failed' and set completed_at."""
        ...
