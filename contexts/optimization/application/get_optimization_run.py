"""get_optimization_run read use case (D111 commitment 2)."""

from __future__ import annotations

from uuid import UUID

from contexts.optimization.ports.optimization_run_reader import (
    OptimizationRunReader,
    OptimizationRunSnapshot,
)
from shared_kernel.tenant_context import TenantContext


async def get_optimization_run(
    *,
    tenant_context: TenantContext,
    run_id: UUID,
    reader: OptimizationRunReader,
) -> OptimizationRunSnapshot | None:
    """Return the optimization-run snapshot or None.

    Cross-tenant access returns None per the tenant-isolation
    contract.
    """
    return await reader.get_optimization_run(
        tenant_context=tenant_context,
        run_id=run_id,
    )


__all__ = ["get_optimization_run"]
