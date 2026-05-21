"""HTTP routes for the portfolio context read surface (D124, S43b).

Two routes:

- ``GET /api/v1/portfolio/cases`` — paginated, filtered list of the
  authenticated tenant's cases.
- ``GET /api/v1/portfolio/cases/{case_id}`` — case detail with its
  DataPoints and each DataPoint's full revision history.

Both carry principal-derived tenant context per the S29b precedent:
the reused ``get_tenant_context`` dependency resolves the principal's
tenant_id; the route calls the use case with the resolved
``TenantContext``.

The case-detail route fires a ``TENANT_SCOPE_VIOLATION`` security
event on every 404 per D98 / S34: the HTTP layer cannot structurally
distinguish a cross-tenant attempt from a genuinely missing case on
the requester's own tenant (the reader returns ``None`` for both).
The list route fires no security event on an empty page — list
no-results is structurally indistinguishable from genuine
no-results. Write-side routes defer to S44.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from apps.api._errors import BoundTenantIdMismatchError, CaseNotFoundError
from apps.api.middleware import get_principal
from apps.api.routers._portfolio_dto import (
    CaseDetailDTO,
    CaseListDTO,
    case_detail_to_dto,
    case_list_to_dto,
)
from apps.api.routers._portfolio_query import parse_case_list_query
from apps.api.routers.inference import get_tenant_context
from contexts.portfolio.application import get_case_detail, list_cases
from contexts.portfolio.application.cursor import encode_case_cursor
from contexts.portfolio.domain.query_filters import (
    CaseListCursor,
    CaseListFilters,
)
from contexts.portfolio.ports import PortfolioReader
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
    SecurityEventLogger,
)
from padhanam.security import Principal
from shared_kernel import TenantContext, TenantId

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


def get_portfolio_reader(request: Request) -> PortfolioReader:
    """FastAPI dependency: pull the configured PortfolioReader off app.state."""
    reader = getattr(request.app.state, "portfolio_reader", None)
    if reader is None:
        raise HTTPException(
            status_code=503,
            detail="portfolio reader not configured on this API instance",
        )
    return reader


def get_security_event_logger(request: Request) -> SecurityEventLogger:
    """FastAPI dependency: pull the security-event logger off app.state."""
    logger = getattr(request.app.state, "security_events", None)
    if logger is None:
        raise HTTPException(
            status_code=503,
            detail="security-event logger not configured on this API instance",
        )
    return logger


@router.get("/cases", response_model=CaseListDTO)
async def list_portfolio_cases(
    parsed: Annotated[
        tuple[CaseListFilters, CaseListCursor | None, int],
        Depends(parse_case_list_query),
    ],
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    reader: Annotated[PortfolioReader, Depends(get_portfolio_reader)],
) -> CaseListDTO:
    """List the authenticated tenant's cases, newest first, paginated."""
    filters, cursor, page_size = parsed
    try:
        page = await list_cases(
            tenant_context=tenant_context,
            reader=reader,
            filters=filters,
            cursor=cursor,
            page_size=page_size,
        )
    except ValueError as exc:
        if "tenant" in str(exc):
            raise BoundTenantIdMismatchError(exc) from exc
        raise
    next_cursor = (
        encode_case_cursor(page.next_cursor)
        if page.next_cursor is not None
        else None
    )
    return case_list_to_dto(page, next_cursor)


@router.get("/cases/{case_id}", response_model=CaseDetailDTO)
async def get_portfolio_case(
    case_id: UUID,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    reader: Annotated[PortfolioReader, Depends(get_portfolio_reader)],
    principal: Annotated[Principal, Depends(get_principal)],
    security_events: Annotated[
        SecurityEventLogger, Depends(get_security_event_logger)
    ],
) -> CaseDetailDTO:
    """Return a Case with its DataPoints and their revision history.

    Returns 404 (with a ``TENANT_SCOPE_VIOLATION`` security event)
    when the case is not present on the principal's tenant — the
    privacy-preserving response per the run-history precedent at S34.
    """
    try:
        detail = await get_case_detail(
            tenant_context=tenant_context, reader=reader, case_id=case_id
        )
    except ValueError as exc:
        if "tenant" in str(exc):
            raise BoundTenantIdMismatchError(exc) from exc
        raise
    if detail is None:
        security_events.emit(
            SecurityEvent(
                category=SecurityEventCategory.TENANT_SCOPE_VIOLATION,
                principal_ref=principal.subject,
                tenant_id=TenantId(str(tenant_context.tenant_id)),
                action=f"GET /api/v1/portfolio/cases/{case_id}",
                resource_ref=str(case_id),
                outcome="not_found",
                metadata={
                    "principal_tenant_id": str(principal.tenant_id),
                    "requested_case_id": str(case_id),
                },
            )
        )
        raise CaseNotFoundError(str(case_id))
    return case_detail_to_dto(detail)
