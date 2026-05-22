"""HTTP routes for the portfolio context (D124, S43b; D126, S44a; D127/D128, S44b).

Read surface (S43b):

- ``GET /api/v1/portfolio/cases`` — paginated, filtered case list.
- ``GET /api/v1/portfolio/cases/{case_id}`` — case detail with
  DataPoints and revision history.

Write surface (S44b) — every write goes through an intake-canonical
orchestration per D128:

- ``POST /api/v1/portfolio/cases`` — record_intake_and_create_case.
- ``POST /api/v1/portfolio/data_points`` — record_intake_and_create_data_point.
- ``PATCH /api/v1/portfolio/data_points/{data_point_id}`` —
  record_intake_and_revise_data_point.

The write paths sit under the existing ``/api/v1/portfolio`` router
prefix, consistent with the S43b read routes (the S44b brief named
``/api/v1/cases`` — reconciled to the established prefix per the
brief-path-drift discipline). Each route resolves a request-scoped
``ActorContext`` via ``get_actor_context``; the orchestrations
enforce authorisation at the use-case boundary, and an
``AuthorisationDenied`` propagates to the 403 handler at
``apps/api/_auth_errors.py``.
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
from apps.api.routers._portfolio_write_dto import (
    CreateCaseRequest,
    CreateCaseResponse,
    CreateDataPointRequest,
    CreateDataPointResponse,
    ReviseDataPointRequest,
    ReviseDataPointResponse,
    case_write_result_to_response,
    data_point_create_result_to_response,
    data_point_revise_result_to_response,
)
from contexts.audit.domain.ports import AuditPort
from contexts.intake.application import (
    record_intake_and_create_case,
    record_intake_and_create_data_point,
    record_intake_and_revise_data_point,
)
from contexts.intake.application.ports.portfolio_writer import PortfolioWriter
from contexts.intake.domain import ManualEntryPayload
from contexts.intake.ports.intake_repository import IntakeRepository
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


def get_intake_repository(request: Request) -> IntakeRepository:
    """FastAPI dependency: pull the configured IntakeRepository off app.state."""
    repo = getattr(request.app.state, "intake_repository", None)
    if repo is None:
        raise HTTPException(
            status_code=503,
            detail="intake repository not configured on this API instance",
        )
    return repo


def get_audit_port(request: Request) -> AuditPort:
    """FastAPI dependency: pull the configured AuditPort off app.state."""
    port = getattr(request.app.state, "audit_port", None)
    if port is None:
        raise HTTPException(
            status_code=503,
            detail="audit port not configured on this API instance",
        )
    return port


def get_portfolio_writer(request: Request) -> PortfolioWriter:
    """FastAPI dependency: pull the configured PortfolioWriter off app.state."""
    writer = getattr(request.app.state, "portfolio_writer", None)
    if writer is None:
        raise HTTPException(
            status_code=503,
            detail="portfolio writer not configured on this API instance",
        )
    return writer


def _payload(body: CreateCaseRequest | CreateDataPointRequest
             | ReviseDataPointRequest) -> ManualEntryPayload:
    """Build the ManualEntryPayload the orchestration records."""
    return ManualEntryPayload(
        raw_text=body.raw_text,
        intent_hint=body.intent_hint,
        linked_case_ids=tuple(body.linked_case_ids),
    )


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
    when the case is not present on the principal's tenant.
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


@router.post("/cases", response_model=CreateCaseResponse, status_code=201)
async def create_portfolio_case(
    body: CreateCaseRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    intake_repository: Annotated[
        IntakeRepository, Depends(get_intake_repository)
    ],
    audit_port: Annotated[AuditPort, Depends(get_audit_port)],
    portfolio_writer: Annotated[
        PortfolioWriter, Depends(get_portfolio_writer)
    ],
) -> CreateCaseResponse:
    """Record an intake and create a Case (D128 intake-canonical)."""
    try:
        result = await record_intake_and_create_case(
            intake_repository=intake_repository,
            audit_port=audit_port,
            portfolio_writer=portfolio_writer,
            actor=actor,
            payload=_payload(body),
            title=body.title,
        )
    except ValueError as exc:
        if "tenant" in str(exc):
            raise BoundTenantIdMismatchError(exc) from exc
        raise
    return case_write_result_to_response(result)


@router.post(
    "/data_points",
    response_model=CreateDataPointResponse,
    status_code=201,
)
async def create_portfolio_data_point(
    body: CreateDataPointRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    intake_repository: Annotated[
        IntakeRepository, Depends(get_intake_repository)
    ],
    audit_port: Annotated[AuditPort, Depends(get_audit_port)],
    portfolio_writer: Annotated[
        PortfolioWriter, Depends(get_portfolio_writer)
    ],
) -> CreateDataPointResponse:
    """Record an intake and create a DataPoint (D128 intake-canonical)."""
    try:
        result = await record_intake_and_create_data_point(
            intake_repository=intake_repository,
            audit_port=audit_port,
            portfolio_writer=portfolio_writer,
            actor=actor,
            payload=_payload(body),
            case_id=body.case_id,
            data_point_type=body.data_point_type.value,
            value=body.value,
        )
    except ValueError as exc:
        if "tenant" in str(exc):
            raise BoundTenantIdMismatchError(exc) from exc
        raise
    return data_point_create_result_to_response(result)


@router.patch(
    "/data_points/{data_point_id}",
    response_model=ReviseDataPointResponse,
)
async def revise_portfolio_data_point(
    data_point_id: UUID,
    body: ReviseDataPointRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    intake_repository: Annotated[
        IntakeRepository, Depends(get_intake_repository)
    ],
    audit_port: Annotated[AuditPort, Depends(get_audit_port)],
    portfolio_writer: Annotated[
        PortfolioWriter, Depends(get_portfolio_writer)
    ],
) -> ReviseDataPointResponse:
    """Record an intake and revise a DataPoint (D128 intake-canonical).

    ``DataPointNotFoundError`` from the orchestration propagates to
    the registered 404 handler.
    """
    try:
        result = await record_intake_and_revise_data_point(
            intake_repository=intake_repository,
            audit_port=audit_port,
            portfolio_writer=portfolio_writer,
            actor=actor,
            payload=_payload(body),
            data_point_id=data_point_id,
            value=body.value,
        )
    except ValueError as exc:
        if "tenant" in str(exc):
            raise BoundTenantIdMismatchError(exc) from exc
        raise
    return data_point_revise_result_to_response(result)
