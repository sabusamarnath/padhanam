"""HTTP routes for the audit read surface (D103, S37).

Four routes across two trees per D103:

- ``GET /audit/events/{event_id}`` and ``GET /audit/events`` —
  per-tenant chain served under the existing
  principal-derived tenant context pattern from S29b/S34. The
  ``get_tenant_context`` dependency at
  ``apps/api/routers/inference.py`` is extended at S37 commit 2
  with a discriminator check that rejects platform-operator
  tokens with the typed ``PrincipalTypeMismatchError`` →
  registered 403 ``principal_type_mismatch`` handler (relocated
  to ``apps/api/_auth_errors.py`` at S38 per D104).

- ``GET /platform/audit/events/{event_id}`` and ``GET /platform/audit/events`` —
  control-plane chain served under the new
  ``get_platform_operator_principal`` dependency at S37 commit 2.
  Tenant tokens are rejected with the same typed error and the
  same 403 path.

Each route invokes the ``AuditEventReader`` port (wired at S36,
exposed on ``app.state.audit_event_reader`` by main.py) with
``destination`` and ``tenant_context`` parameters per D102's
destination-parameter routing:

- Per-tenant routes pass ``destination="per_tenant"`` and the
  resolved ``TenantContext``.
- Control-plane routes pass ``destination="control_plane"`` and
  ``tenant_context=None``.

Two FastAPI routers ship from this module — one under each path
prefix — so each route tree's authorization decision is visible
at route declaration per D103's two-tree-shape reasoning. The
composition root at ``apps/api/main.py`` includes both routers.

The list routes consume the shared ``parse_audit_list_query``
sub-dependency from ``_audit_query.py``. Validation failures
raise typed exceptions that the registered handlers at
``apps/api/_errors.py`` translate to 400. The single-event
routes catch the reader returning ``None`` and raise
``AuditEventNotFoundError`` → 404 ``audit_event_not_found``.

Security event firing on the 403 path happens in the error
handler (commit 4) per the centralised-emission shape; route
handlers do not fire security events themselves at this
altitude because the 403 cases are gated upstream of the route
body and the 404 case is privacy-preserving (cross-tenant
invisibility is structurally indistinguishable from genuine
not-found at the per-tenant destination).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from apps.api._errors import AuditEventNotFoundError
from apps.api.middleware import get_platform_operator_principal
from apps.api.routers._audit_dto import (
    AuditEventListPageDTO,
    AuditEventRecordDTO,
    ChainIntegrityVerificationDTO,
)
from apps.api.routers._audit_query import parse_audit_list_query
from apps.api.routers.inference import get_tenant_context
from contexts.audit.application.cursor import encode as encode_cursor
from contexts.audit.domain.query_filters import (
    AuditEventListCursor,
    AuditEventListFilters,
)
from contexts.audit.ports.reader import AuditEventReader
from padhanam.security import PlatformOperatorPrincipal
from shared_kernel import TenantContext


tenant_router = APIRouter(prefix="/audit", tags=["audit", "tenant"])
platform_router = APIRouter(
    prefix="/platform/audit", tags=["audit", "platform-operator"]
)


def get_audit_event_reader(request: Request) -> AuditEventReader:
    """FastAPI dependency: pull the configured AuditEventReader off app.state.

    ``apps/api/main.py`` registers the reader on
    ``app.state.audit_event_reader`` at application factory time
    (S37). Returns 503 if no reader is wired so test fixtures
    without the audit stack can still construct an app without
    breaking the dependency-resolution path.
    """
    reader = getattr(request.app.state, "audit_event_reader", None)
    if reader is None:
        # The dependency raises HTTPException(503) rather than a typed
        # exception because the 503 path is configuration-shaped (not
        # a typed domain failure) and the run-history precedent at
        # apps/api/routers/run_history.py:get_run_history_reader uses
        # the same shape.
        from fastapi import HTTPException

        raise HTTPException(
            status_code=503,
            detail="audit event reader not configured on this API instance",
        )
    return reader


# --------------------------------------------------------------------
# Per-tenant routes — /audit/*
# --------------------------------------------------------------------


@tenant_router.get("/events/{event_id}", response_model=AuditEventRecordDTO)
async def get_tenant_audit_event(
    event_id: UUID,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    reader: Annotated[AuditEventReader, Depends(get_audit_event_reader)],
) -> AuditEventRecordDTO:
    """Return one audit event from the per-tenant chain.

    The ``get_tenant_context`` dependency enforces principal-type
    gating (rejects platform-operator with 403) and registry
    resolution (rejects non-UUID with 400, missing with 404).
    """
    record = await reader.get_audit_event(
        destination="per_tenant",
        event_id=event_id,
        tenant_context=tenant_context,
    )
    if record is None:
        raise AuditEventNotFoundError(str(event_id))
    return AuditEventRecordDTO.model_validate(record)


@tenant_router.get("/events", response_model=AuditEventListPageDTO)
async def list_tenant_audit_events(
    parsed: Annotated[
        tuple[AuditEventListFilters, AuditEventListCursor | None, int],
        Depends(parse_audit_list_query),
    ],
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    reader: Annotated[AuditEventReader, Depends(get_audit_event_reader)],
) -> AuditEventListPageDTO:
    """Return a filtered page from the per-tenant chain.

    Filters travel independently of cursor per the run-history
    precedent at D98 — server honours both; client is responsible
    for filter consistency across paginated calls. Empty page is
    returned when no events match (no security event fires
    because list-no-results is structurally indistinguishable
    from genuine no-results at this altitude).
    """
    filters, cursor, page_size = parsed
    page = await reader.list_audit_events_with_filters(
        destination="per_tenant",
        filters=filters,
        cursor=cursor,
        page_size=page_size,
        tenant_context=tenant_context,
    )
    return AuditEventListPageDTO(
        events=[AuditEventRecordDTO.model_validate(e) for e in page.events],
        next_cursor=encode_cursor(page.next_cursor) if page.next_cursor else None,
        chain_integrity=ChainIntegrityVerificationDTO.model_validate(
            page.chain_integrity
        ),
    )


# --------------------------------------------------------------------
# Control-plane routes — /platform/audit/*
# --------------------------------------------------------------------


@platform_router.get(
    "/events/{event_id}", response_model=AuditEventRecordDTO
)
async def get_platform_audit_event(
    event_id: UUID,
    _principal: Annotated[
        PlatformOperatorPrincipal, Depends(get_platform_operator_principal)
    ],
    reader: Annotated[AuditEventReader, Depends(get_audit_event_reader)],
) -> AuditEventRecordDTO:
    """Return one audit event from the control-plane chain.

    The ``get_platform_operator_principal`` dependency enforces
    principal-type gating (rejects tenant with 403). No tenant
    context flows; ``destination='control_plane'`` routes the
    query to the control-plane ``tenant_audit`` table.
    """
    record = await reader.get_audit_event(
        destination="control_plane",
        event_id=event_id,
        tenant_context=None,
    )
    if record is None:
        raise AuditEventNotFoundError(str(event_id))
    return AuditEventRecordDTO.model_validate(record)


@platform_router.get("/events", response_model=AuditEventListPageDTO)
async def list_platform_audit_events(
    parsed: Annotated[
        tuple[AuditEventListFilters, AuditEventListCursor | None, int],
        Depends(parse_audit_list_query),
    ],
    _principal: Annotated[
        PlatformOperatorPrincipal, Depends(get_platform_operator_principal)
    ],
    reader: Annotated[AuditEventReader, Depends(get_audit_event_reader)],
) -> AuditEventListPageDTO:
    """Return a filtered page from the control-plane chain."""
    filters, cursor, page_size = parsed
    page = await reader.list_audit_events_with_filters(
        destination="control_plane",
        filters=filters,
        cursor=cursor,
        page_size=page_size,
        tenant_context=None,
    )
    return AuditEventListPageDTO(
        events=[AuditEventRecordDTO.model_validate(e) for e in page.events],
        next_cursor=encode_cursor(page.next_cursor) if page.next_cursor else None,
        chain_integrity=ChainIntegrityVerificationDTO.model_validate(
            page.chain_integrity
        ),
    )


__all__ = ["get_audit_event_reader", "platform_router", "tenant_router"]
