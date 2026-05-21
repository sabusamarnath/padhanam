"""HTTP routes for the portfolio context read surface (D124, S43b; D126, S44a).

Two routes:

- ``GET /api/v1/portfolio/cases`` — paginated, filtered list of the
  authenticated tenant's cases.
- ``GET /api/v1/portfolio/cases/{case_id}`` — case detail with its
  DataPoints and each DataPoint's full revision history.

S44a (D126): both routes resolve a request-scoped ``ActorContext``
via the ``get_actor_context`` dependency and pass it to the use
cases, which enforce authorisation at the use-case boundary. The
``get_actor_context`` dependency composes the registry-resolved
TenantContext with the Principal-derived actor identity; an
``AuthorisationDenied`` raised by a use case propagates to the
registered handler at ``apps/api/_auth_errors.py``, which returns
403 per D126.

The case-detail route fires a ``TENANT_SCOPE_VIOLATION`` security
event on every 404 per D98 / S34: the HTTP layer cannot structurally
distinguish a cross-tenant attempt from a genuinely missing case on
the requester's own tenant (the reader returns ``None`` for both).
The list route fires no security event on an empty page — list
no-results is structurally indistinguishable from genuine
no-results. Write-side routes defer to S44b.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from apps.api._errors import BoundTenantIdMismatchError, CaseNotFoundError
from apps.api.middleware import get_actor_context
from apps.api.routers._portfolio_dto import (
    CaseDetailDTO,
    CaseListDTO,
    case_detail_to_dto,
    case_list_to_dto,
)
from apps.api.routers._portfolio_query import parse_case_list_query
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
from shared_kernel import ActorContext, TenantId

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
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    reader: Annotated[PortfolioReader, Depends(get_portfolio_reader)],
) -> CaseListDTO:
    """List the authenticated tenant's cases, newest first, paginated."""
    filters, cursor, page_size = parsed
    try:
        page = await list_cases(
            reader=reader,
            actor=actor,
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
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    reader: Annotated[PortfolioReader, Depends(get_portfolio_reader)],
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
            reader=reader, actor=actor, case_id=case_id
        )
    except ValueError as exc:
        if "tenant" in str(exc):
            raise BoundTenantIdMismatchError(exc) from exc
        raise
    if detail is None:
        tenant_id = str(actor.tenant_context.tenant_id)
        security_events.emit(
            SecurityEvent(
                category=SecurityEventCategory.TENANT_SCOPE_VIOLATION,
                principal_ref=actor.actor_id,
                tenant_id=TenantId(tenant_id),
                action=f"GET /api/v1/portfolio/cases/{case_id}",
                resource_ref=str(case_id),
                outcome="not_found",
                metadata={
                    "principal_tenant_id": tenant_id,
                    "requested_case_id": str(case_id),
                },
            )
        )
        raise CaseNotFoundError(str(case_id))
    return case_detail_to_dto(detail)
