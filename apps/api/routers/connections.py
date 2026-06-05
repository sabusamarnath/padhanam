"""HTTP routes for the in-product Connections page (D159, design-language §9).

- ``GET /api/v1/connections`` — the tenant's connection status: whether
  Google Calendar is connected, the read-only scope, the calendar-to-domain
  tag, and the other connectable providers (mail, Drive) that render per §9
  but are not wired into the Today list this slice.
- ``GET /connections`` — the served Connections page (auth-exempt per
  ``_PUBLIC_PATHS``; the page carries a dev-token field and makes
  authenticated fetches to the status route, the ``/app`` pattern).

The status route resolves a request-scoped ``ActorContext`` so the
connection state is the actor's own tenant's (D12). The OAuth connect
itself is operator-gated (the self-hosted Nango connect flow; AC8 in the
smoke); this surface reports state and carries the read-only posture
(D148), it does not mint tokens.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from apps.api._calendar_connect_wiring import (
    CalendarConnectInitiator,
    ConnectError,
    ConnectionStore,
)
from apps.api._connections_wiring import ConnectionsStatusReader
from apps.api.middleware import get_actor_context
from apps.api.routers._connections_dto import (
    ConnectCallbackRequest,
    ConnectSessionDTO,
    ConnectionsStatusDTO,
    StoredConnectionDTO,
    connections_view_to_dto,
)
from shared_kernel import ActorContext

router = APIRouter(prefix="/api/v1/connections", tags=["connections"])
ui_router = APIRouter(tags=["connections-ui"])

_PAGE_PATH = Path(__file__).resolve().parent.parent / "static" / "connections.html"


def get_connections_status_reader(request: Request) -> ConnectionsStatusReader:
    """FastAPI dependency: the Connections status reader."""
    value = getattr(request.app.state, "connections_status_reader", None)
    if value is None:
        raise HTTPException(
            status_code=503,
            detail="connections_status_reader not configured on this API instance",
        )
    return value  # type: ignore[return-value]


def get_calendar_connect_initiator(request: Request) -> CalendarConnectInitiator:
    """FastAPI dependency: the calendar connect initiator (D160)."""
    value = getattr(request.app.state, "calendar_connect_initiator", None)
    if value is None:
        raise HTTPException(
            status_code=503,
            detail="calendar_connect_initiator not configured",
        )
    return value  # type: ignore[return-value]


def get_connection_store(request: Request) -> ConnectionStore:
    """FastAPI dependency: the connect-callback connection store (D160)."""
    value = getattr(request.app.state, "connection_store", None)
    if value is None:
        raise HTTPException(
            status_code=503, detail="connection_store not configured"
        )
    return value  # type: ignore[return-value]


@router.get("", response_model=ConnectionsStatusDTO)
async def get_connections(
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    reader: Annotated[
        ConnectionsStatusReader, Depends(get_connections_status_reader)
    ],
) -> ConnectionsStatusDTO:
    """Return the actor's tenant connection status (D159, §9)."""
    view = await reader.status(actor=actor)
    return connections_view_to_dto(view)


@router.post("/calendar/initiate", response_model=ConnectSessionDTO)
async def initiate_calendar_connect(
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    initiator: Annotated[
        CalendarConnectInitiator, Depends(get_calendar_connect_initiator)
    ],
) -> ConnectSessionDTO:
    """Create a calendar connect session (D160; the Nango adapter is operator-gated)."""
    try:
        session = await initiator.create_session(actor=actor)
    except ConnectError as exc:
        # Operator-gated until the Nango connect-session creator is wired.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ConnectSessionDTO(
        provider_config_key=session.provider_config_key,
        connect_url=session.connect_url,
        session_token=session.session_token,
    )


@router.post("/calendar/callback", response_model=StoredConnectionDTO)
async def calendar_connect_callback(
    body: ConnectCallbackRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    store: Annotated[ConnectionStore, Depends(get_connection_store)],
) -> StoredConnectionDTO:
    """Store the per-tenant connection the connect flow issued, then first-sync (D160)."""
    try:
        result = await store.store_connection(
            actor=actor, provider_connection_ref=body.provider_connection_ref
        )
    except ConnectError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return StoredConnectionDTO(
        connection_id=str(result.connection_id),
        synced=result.synced,
        sync_error=result.sync_error,
    )


@ui_router.get("/connections", include_in_schema=False)
async def connections_page() -> FileResponse:
    """Serve the self-contained Connections page (auth-exempt)."""
    return FileResponse(_PAGE_PATH, media_type="text/html")


__all__ = ["router", "ui_router"]
