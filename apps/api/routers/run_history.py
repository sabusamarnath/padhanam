"""HTTP routes for the run-history read surface (D98, S34).

Two routes:

- ``GET /runs/{run_id}`` — single run with chunk and entity citations.
- ``GET /runs`` — paginated, filtered list of runs (no citations
  attached at list-view altitude per D97's bounded-cardinality
  argument).

Both routes carry principal-derived tenant context per the S29b
precedent at ``apps/api/routers/agent.py``: the authentication
middleware sets ``request.state.principal``; the reused
``get_tenant_context`` dependency from
``apps/api/routers/inference.py`` resolves the principal's tenant_id
against the control-plane registry; the route handler calls the
reader with the resolved ``TenantContext``.

Security event firing on 404 from ``GET /runs/{run_id}``: the HTTP
layer cannot structurally distinguish a cross-tenant attempt from a
genuinely missing run on the requester's own tenant (the reader
returns ``None`` for both). The route fires a
``TENANT_SCOPE_VIOLATION`` security event on every 404 with the
principal's tenant_id and the requested run_id logged for forensic
correlation per D98; a SIEM downstream can distinguish patterns
(many 404s from one principal across distinct run-ids vs. occasional
404s) at its own altitude.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from apps.api._errors import BoundTenantIdMismatchError, RunNotFoundError
from apps.api.middleware import get_principal
from apps.api.routers._run_history_dto import (
    RunListResponse,
    RunResponse,
)
from apps.api.routers._run_history_query import parse_run_list_query
from apps.api.routers.inference import get_tenant_context
from contexts.run_history.application.cursor import encode as encode_cursor
from contexts.run_history.domain.query_filters import (
    RunListCursor,
    RunListFilters,
)
from contexts.run_history.ports.reader import RunHistoryReader
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
    SecurityEventLogger,
)
from padhanam.security import Principal
from shared_kernel import TenantContext, TenantId


router = APIRouter(prefix="/runs", tags=["run-history"])


def get_run_history_reader(request: Request) -> RunHistoryReader:
    """FastAPI dependency: pull the configured RunHistoryReader off app.state.

    apps/api/main.py registers the reader on app.state.run_history_reader
    at application factory time. Returns 503 if no reader is wired
    (e.g., apps without the run-history stack configured for tests).
    """
    reader = getattr(request.app.state, "run_history_reader", None)
    if reader is None:
        raise HTTPException(
            status_code=503,
            detail="run-history reader not configured on this API instance",
        )
    return reader


def get_security_event_logger(request: Request) -> SecurityEventLogger:
    """Pull the configured security-event logger off app.state.

    Set by apps/api/main.py during composition; tests substitute via
    ``app.dependency_overrides`` to capture emitted events for
    assertion.
    """
    logger = getattr(request.app.state, "security_events", None)
    if logger is None:
        raise HTTPException(
            status_code=503,
            detail="security-event logger not configured on this API instance",
        )
    return logger


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: UUID,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    reader: Annotated[RunHistoryReader, Depends(get_run_history_reader)],
    principal: Annotated[Principal, Depends(get_principal)],
    security_events: Annotated[
        SecurityEventLogger, Depends(get_security_event_logger)
    ],
) -> RunResponse:
    """Return the run as an aggregate with citations attached.

    Returns 404 (with ``TENANT_SCOPE_VIOLATION`` security event) when
    the run-id is not present on the principal's tenant; the response
    is privacy-preserving — confirming existence on another tenant
    would leak information.
    """
    try:
        record = await reader.get_run(
            tenant_context=tenant_context, run_id=run_id
        )
    except ValueError as exc:
        # Reader's bound-tenant-id defence-in-depth fired; should never
        # happen above the data layer because the route-layer principal
        # check should have caught the mismatch. Re-raise as the typed
        # exception so the handler at apps/api/_errors.py emits the
        # security event synchronously and returns 500.
        if "tenant" in str(exc):
            raise BoundTenantIdMismatchError(exc) from exc
        raise

    if record is None:
        security_events.emit(
            SecurityEvent(
                category=SecurityEventCategory.TENANT_SCOPE_VIOLATION,
                principal_ref=principal.subject,
                tenant_id=TenantId(str(tenant_context.tenant_id)),
                action=f"GET /runs/{run_id}",
                resource_ref=str(run_id),
                outcome="not_found",
                metadata={
                    "principal_tenant_id": str(principal.tenant_id),
                    "requested_run_id": str(run_id),
                },
            )
        )
        raise RunNotFoundError(str(run_id))
    return RunResponse.model_validate(record)


@router.get("", response_model=RunListResponse)
async def list_runs(
    parsed: Annotated[
        tuple[RunListFilters, RunListCursor | None],
        Depends(parse_run_list_query),
    ],
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    reader: Annotated[RunHistoryReader, Depends(get_run_history_reader)],
) -> RunListResponse:
    """Return a page of runs filtered by query params.

    Filters and cursor travel independently per D98 — server honours
    both; client is responsible for filter consistency across
    paginated calls. Empty list is returned when no runs match
    (whether by filter or by cross-tenant invisibility); no security
    event fires because list-no-results is structurally
    indistinguishable from genuine no-results.
    """
    filters, cursor = parsed
    try:
        page = await reader.list_runs_with_filters(
            tenant_context=tenant_context,
            filters=filters,
            cursor=cursor,
        )
    except ValueError as exc:
        if "tenant" in str(exc):
            raise BoundTenantIdMismatchError(exc) from exc
        raise

    return RunListResponse(
        runs=[RunResponse.model_validate(run) for run in page.runs],
        next_cursor=encode_cursor(page.next_cursor) if page.next_cursor else None,
    )
