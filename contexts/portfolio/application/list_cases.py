"""list_cases read use case (D124, D126).

A thin read use case over the PortfolioReader's paginated case
surface. Cursor decoding happens at the transport boundary (CLI /
HTTP); this use case receives a decoded ``CaseListCursor``.

S44a (D126): the use case accepts an ActorContext, applies the
``requires_authorisation`` decorator, and extracts
``actor.tenant_context`` for the reader call.
"""

from __future__ import annotations

from contexts.portfolio.domain.query_filters import (
    CaseListCursor,
    CaseListFilters,
)
from contexts.portfolio.ports import CaseListPage, PortfolioReader
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    PORTFOLIO_CASE_LIST,
    requires_authorisation,
)

_DEFAULT_PAGE_SIZE: int = 20


@requires_authorisation(PORTFOLIO_CASE_LIST)
async def list_cases(
    *,
    reader: PortfolioReader,
    actor: ActorContext,
    filters: CaseListFilters | None = None,
    cursor: CaseListCursor | None = None,
    page_size: int = _DEFAULT_PAGE_SIZE,
) -> CaseListPage:
    """Return a paginated page of the tenant's cases."""
    return await reader.list_cases(
        tenant_context=actor.tenant_context,
        filters=filters,
        cursor=cursor,
        page_size=page_size,
    )


__all__ = ["list_cases"]
