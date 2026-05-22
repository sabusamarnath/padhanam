"""HTTP routes for the intake context (D127, D128, S44b).

Three routes — the standalone intake surface:

- ``POST /api/v1/intakes`` — record an IntakeRecord (the
  operator-records-without-acting path; the canonical path for
  calendar-read / email-read intake at P14).
- ``GET /api/v1/intakes/{intake_id}`` — single-record read.
- ``GET /api/v1/intakes`` — paginated, source-filtered list.

Each route resolves a request-scoped ``ActorContext`` via
``get_actor_context``; the use cases enforce authorisation at the
use-case boundary, and an ``AuthorisationDenied`` propagates to the
403 handler at ``apps/api/_auth_errors.py``.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from apps.api._errors import BoundTenantIdMismatchError, IntakeNotFoundError
from apps.api.middleware import get_actor_context
from apps.api.routers._intake_dto import (
    IntakeListResponse,
    IntakeResponse,
    RecordIntakeRequest,
    intake_list_to_response,
    intake_to_response,
)
from apps.api.routers._intake_query import parse_intake_list_query
from contexts.audit.domain.ports import AuditPort
from contexts.intake.application import get_intake, list_intakes, record_intake
from contexts.intake.application.cursor import encode_intake_cursor
from contexts.intake.domain import IntakeSource, ManualEntryPayload
from contexts.intake.domain.query_filters import (
    IntakeListCursor,
    IntakeListFilters,
)
from contexts.intake.ports.intake_repository import IntakeRepository
from shared_kernel import ActorContext

router = APIRouter(prefix="/api/v1/intakes", tags=["intake"])


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


@router.post("", response_model=IntakeResponse, status_code=201)
async def record_intake_route(
    body: RecordIntakeRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    intake_repository: Annotated[
        IntakeRepository, Depends(get_intake_repository)
    ],
    audit_port: Annotated[AuditPort, Depends(get_audit_port)],
) -> IntakeResponse:
    """Record an IntakeRecord on the standalone path."""
    payload = ManualEntryPayload(
        raw_text=body.raw_text,
        intent_hint=body.intent_hint,
        linked_case_ids=tuple(body.linked_case_ids),
    )
    try:
        intake = await record_intake(
            repository=intake_repository,
            audit_port=audit_port,
            actor=actor,
            intake_source=IntakeSource(body.intake_source.value),
            payload=payload,
        )
    except ValueError as exc:
        if "tenant" in str(exc):
            raise BoundTenantIdMismatchError(exc) from exc
        raise
    return intake_to_response(intake)


@router.get("/{intake_id}", response_model=IntakeResponse)
async def get_intake_route(
    intake_id: UUID,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    intake_repository: Annotated[
        IntakeRepository, Depends(get_intake_repository)
    ],
) -> IntakeResponse:
    """Return the IntakeRecord, or 404 when absent for the tenant."""
    try:
        intake = await get_intake(
            repository=intake_repository, actor=actor, intake_id=intake_id
        )
    except ValueError as exc:
        if "tenant" in str(exc):
            raise BoundTenantIdMismatchError(exc) from exc
        raise
    if intake is None:
        raise IntakeNotFoundError(str(intake_id))
    return intake_to_response(intake)


@router.get("", response_model=IntakeListResponse)
async def list_intakes_route(
    parsed: Annotated[
        tuple[IntakeListFilters, IntakeListCursor | None, int],
        Depends(parse_intake_list_query),
    ],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    intake_repository: Annotated[
        IntakeRepository, Depends(get_intake_repository)
    ],
) -> IntakeListResponse:
    """List the authenticated tenant's intakes, newest first, paginated."""
    filters, cursor, page_size = parsed
    try:
        page = await list_intakes(
            repository=intake_repository,
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
        encode_intake_cursor(page.next_cursor)
        if page.next_cursor is not None
        else None
    )
    return intake_list_to_response(page, next_cursor)
