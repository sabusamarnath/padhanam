"""list_optimization_runs read use case (D111 commitment 2)."""

from __future__ import annotations

from contexts.optimization.application.cursors import (
    decode_optimization_run_cursor,
    encode_optimization_run_cursor,
)
from contexts.optimization.domain.query_filters import PAGE_SIZE_CEILING
from contexts.optimization.ports.optimization_run_reader import (
    OptimizationRunListPage,
    OptimizationRunReader,
)
from shared_kernel.tenant_context import TenantContext


async def list_optimization_runs(
    *,
    tenant_context: TenantContext,
    reader: OptimizationRunReader,
    encoded_cursor: str | None,
    page_size: int,
) -> tuple[OptimizationRunListPage, str | None]:
    """List optimization runs paginated.

    Returns the page plus the optional next-cursor encoded string.
    """
    if not (1 <= page_size <= PAGE_SIZE_CEILING):
        raise ValueError(
            f"page_size must be in [1, {PAGE_SIZE_CEILING}]; got {page_size}"
        )
    cursor = (
        decode_optimization_run_cursor(encoded_cursor)
        if encoded_cursor
        else None
    )
    page = await reader.list_optimization_runs(
        tenant_context=tenant_context,
        cursor=cursor,
        page_size=page_size,
    )
    next_encoded = (
        encode_optimization_run_cursor(page.next_cursor)
        if page.next_cursor is not None
        else None
    )
    return page, next_encoded


__all__ = ["list_optimization_runs"]
