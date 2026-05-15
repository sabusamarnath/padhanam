"""Write-side port for the OptimizationRun aggregate (D111 cmt 2).

The engine persists a ``running`` row at invocation start, marks
``completed`` on success or ``failed`` on uncaught exception. The
``mark_completed`` method also persists the structured skip-reasons
captured during rule iteration.

Ports layer is pure per D16 — no SQLAlchemy, no asyncpg.
"""

from __future__ import annotations

from datetime import datetime
from typing import Mapping, Protocol
from uuid import UUID

from contexts.optimization.domain import CategorySkipReason, OptimizationRun
from shared_kernel.tenant_context import TenantContext


class OptimizationRunRepository(Protocol):
    """Write-side persistence for OptimizationRun."""

    async def persist_run(
        self,
        *,
        tenant_context: TenantContext,
        run: OptimizationRun,
    ) -> None:
        """Insert a new optimization-run row in ``running`` state."""
        ...

    async def mark_completed(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
        completed_at: datetime,
        skipped_categories: Mapping[str, CategorySkipReason],
    ) -> None:
        """Transition an existing ``running`` row to ``completed``.

        Persists ``skipped_categories`` as JSONB; the engine captures
        these during rule iteration when a rule raises
        ``SubstrateGapError``.
        """
        ...

    async def mark_failed(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
        completed_at: datetime,
    ) -> None:
        """Transition an existing ``running`` row to ``failed``."""
        ...


__all__ = ["OptimizationRunRepository"]
