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

from apps.api._connections_wiring import ConnectionsStatusReader
from apps.api.middleware import get_actor_context
from apps.api.routers._connections_dto import (
    ConnectionsStatusDTO,
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


@ui_router.get("/connections", include_in_schema=False)
async def connections_page() -> FileResponse:
    """Serve the self-contained Connections page (auth-exempt)."""
    return FileResponse(_PAGE_PATH, media_type="text/html")


__all__ = ["router", "ui_router"]
