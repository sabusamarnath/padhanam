"""list_cases read use case (D124).

A thin read use case over the PortfolioReader's paginated case
surface. Cursor decoding happens at the transport boundary (CLI /
HTTP); this use case receives a decoded ``CaseListCursor``.
"""

from __future__ import annotations

from contexts.portfolio.domain.query_filters import (
    CaseListCursor,
    CaseListFilters,
)
from contexts.portfolio.ports import CaseListPage, PortfolioReader
from shared_kernel import TenantContext

_DEFAULT_PAGE_SIZE: int = 20


async def list_cases(
    *,
    tenant_context: TenantContext,
    reader: PortfolioReader,
    filters: CaseListFilters | None = None,
    cursor: CaseListCursor | None = None,
    page_size: int = _DEFAULT_PAGE_SIZE,
) -> CaseListPage:
    """Return a paginated page of the tenant's cases."""
    return await reader.list_cases(
        tenant_context=tenant_context,
        filters=filters,
        cursor=cursor,
        page_size=page_size,
    )


__all__ = ["list_cases"]
