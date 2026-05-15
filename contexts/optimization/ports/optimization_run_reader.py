"""Read-side port for OptimizationRun queries (D111 cmt 2).

Two methods:

- ``get_optimization_run`` returns the run aggregate (no children
  — recommendations are queried separately via the recommendation
  reader filtered by ``generated_by_run_id`` if needed).
- ``list_optimization_runs`` returns a paginated page of run
  aggregates plus the optional next cursor.

Tenant scoping flows through ``TenantContext``. Cross-tenant reads
return ``None`` / empty pages per the tenant-isolation contract.

Ports layer is pure per D16 — no SQLAlchemy, no asyncpg.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from contexts.optimization.domain import OptimizationRun
from contexts.optimization.domain.query_filters import (
    OptimizationRunListCursor,
)
from shared_kernel.tenant_context import TenantContext


@dataclass(frozen=True)
class OptimizationRunSnapshot:
    """Snapshot returned by ``get_optimization_run``."""

    run: OptimizationRun


@dataclass(frozen=True)
class OptimizationRunListPage:
    """One page of ``list_optimization_runs`` output."""

    runs: tuple[OptimizationRun, ...]
    next_cursor: OptimizationRunListCursor | None


class OptimizationRunReader(Protocol):
    """Read-side query port for OptimizationRun."""

    async def get_optimization_run(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
    ) -> OptimizationRunSnapshot | None:
        """Return the optimization-run aggregate or None.

        Returns None when the run does not exist or belongs to a
        different tenant (tenant_isolation contract).
        """
        ...

    async def list_optimization_runs(
        self,
        *,
        tenant_context: TenantContext,
        cursor: OptimizationRunListCursor | None,
        page_size: int,
    ) -> OptimizationRunListPage:
        """List optimization runs for a tenant, paginated.

        Sort order is fixed at ``invoked_at DESC, id DESC``;
        tuple-comparison cursor pagination mirrors the run-history
        and retrieval-evaluation reader patterns.
        """
        ...


__all__ = [
    "OptimizationRunListPage",
    "OptimizationRunReader",
    "OptimizationRunSnapshot",
]
