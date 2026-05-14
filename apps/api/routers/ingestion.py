"""HTTP routes for the ingestion management read surface (D104, S38).

Three routes under ``/ingestion``:

- ``GET /ingestion/sources/{source_id}`` — single source lookup.
- ``GET /ingestion/sources`` — paginated source list with cursor
  pagination.
- ``GET /ingestion/sources/{source_id}/status`` — projection of the
  source's pipeline state plus the three error-text fields.

All three routes carry principal-derived tenant context per the
S29b / S34 / S37 precedent: the authentication middleware sets
``request.state.principal``; the reused ``get_tenant_context``
dependency at ``apps/api/routers/inference.py`` resolves the
principal's tenant_id against the control-plane registry (rejects
platform-operator tokens with 403 ``principal_type_mismatch`` per
D103 / D104); the route handler delegates to the
``SourceRepositoryPort`` use cases scoped to the resolved tenant.

Per Path A from S38 reconciliation, the routes consume the existing
ingestion application use cases (``get_source``, ``list_sources``)
directly. No consumer-defined reader port lands at S38; the
extension to ``SourceRepositoryPort`` (commit 3) made list-with-
pagination available alongside the existing get-by-id.

Security event firing on 404: the per-tenant repository scopes
every query by ``tenant_id`` so cross-tenant attempts are
structurally indistinguishable from genuine not-found at the
single-source-lookup altitude. No security event fires from the
route body; mirror of the audit ``get_audit_event`` 404 path per
D103 commit-4 commentary.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from apps.api._errors import IngestionSourceNotFoundError
from apps.api._agent_runtime_wiring import TenantRoutingSourceRepository
from apps.api.routers._ingestion_dto import (
    SourceDTO,
    SourceListPageDTO,
    SourceStatusDTO,
    source_to_dto,
    source_to_status_dto,
)
from apps.api.routers._ingestion_query import parse_source_list_query
from apps.api.routers.inference import get_tenant_context
from contexts.ingestion.application.cursor import encode as encode_cursor
from contexts.ingestion.application.get_source import get_source as get_source_use_case
from contexts.ingestion.application.list_sources import (
    list_sources as list_sources_use_case,
)
from contexts.ingestion.domain.source_list import SourceListCursor
from shared_kernel import TenantContext


router = APIRouter(prefix="/ingestion", tags=["ingestion"])


def get_source_repository(request: Request) -> TenantRoutingSourceRepository:
    """FastAPI dependency: pull the configured source repository off app.state.

    ``apps/api/main.py`` registers the routing repository on
    ``app.state.source_repository`` at application factory time
    (S38). Returns 503 if no repository is wired so test fixtures
    without the ingestion stack can still construct an app without
    breaking the dependency-resolution path. Mirror of the audit
    and run-history reader dependency-resolution shape.
    """
    repo = getattr(request.app.state, "source_repository", None)
    if repo is None:
        raise HTTPException(
            status_code=503,
            detail="source repository not configured on this API instance",
        )
    return repo


@router.get("/sources/{source_id}", response_model=SourceDTO)
async def get_source_route(
    source_id: UUID,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    repository: Annotated[
        TenantRoutingSourceRepository, Depends(get_source_repository)
    ],
) -> SourceDTO:
    """Return one source by id, scoped to the requester's tenant.

    The ``get_tenant_context`` dependency enforces principal-type
    gating (rejects platform-operator with 403) and registry
    resolution (rejects non-UUID with 400, missing with 404). The
    repository scopes the query by tenant_id so cross-tenant
    attempts via fabricated source_id return 404.
    """
    try:
        source = await get_source_use_case(
            repository=repository,
            source_id=source_id,
            tenant_id=str(tenant_context.tenant_id),
        )
    except LookupError as exc:
        raise IngestionSourceNotFoundError(str(source_id)) from exc
    return source_to_dto(source)


@router.get("/sources", response_model=SourceListPageDTO)
async def list_sources_route(
    parsed: Annotated[
        tuple[SourceListCursor | None, int],
        Depends(parse_source_list_query),
    ],
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    repository: Annotated[
        TenantRoutingSourceRepository, Depends(get_source_repository)
    ],
) -> SourceListPageDTO:
    """Return a paginated page of sources scoped to the requester's tenant.

    Empty page is returned when no sources match for the tenant; no
    security event fires because list-no-results is structurally
    indistinguishable from genuine no-results at this altitude.
    Cursor pagination uses tuple comparison on ``(created_at, id)``
    under the ``(DESC, DESC)`` sort order per the adapter
    implementation.
    """
    cursor, page_size = parsed
    page = await list_sources_use_case(
        repository=repository,
        tenant_id=str(tenant_context.tenant_id),
        cursor=cursor,
        page_size=page_size,
    )
    return SourceListPageDTO(
        sources=[source_to_dto(source) for source in page.sources],
        next_cursor=encode_cursor(page.next_cursor) if page.next_cursor else None,
    )


@router.get(
    "/sources/{source_id}/status", response_model=SourceStatusDTO
)
async def get_source_status_route(
    source_id: UUID,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    repository: Annotated[
        TenantRoutingSourceRepository, Depends(get_source_repository)
    ],
) -> SourceStatusDTO:
    """Return the pipeline status surface for one source.

    Per Path A from S38 reconciliation, the status route projects
    the source aggregate's state-relevant fields rather than
    introducing a separate ``get_source_status`` application use
    case. The HTTP boundary holds the projection responsibility.
    """
    try:
        source = await get_source_use_case(
            repository=repository,
            source_id=source_id,
            tenant_id=str(tenant_context.tenant_id),
        )
    except LookupError as exc:
        raise IngestionSourceNotFoundError(str(source_id)) from exc
    return source_to_status_dto(source)


__all__ = ["get_source_repository", "router"]
