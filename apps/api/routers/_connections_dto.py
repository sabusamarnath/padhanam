"""HTTP DTOs for the Connections page (D159, design-language §9)."""

from __future__ import annotations

from pydantic import BaseModel

from apps.api._connections_wiring import ConnectionsView


class ConnectionStatusDTO(BaseModel):
    """One connectable provider's state."""

    provider: str
    name: str
    connected: bool
    read_only_scope: str | None
    domain_tag: str | None
    list_wired: bool


class ConnectionsStatusDTO(BaseModel):
    """The Connections page state: the calendar plus other connectable providers."""

    calendar: ConnectionStatusDTO
    others: list[ConnectionStatusDTO]


def connections_view_to_dto(view: ConnectionsView) -> ConnectionsStatusDTO:
    """Encode the wiring-layer connections view into the HTTP DTO."""

    def _one(status) -> ConnectionStatusDTO:
        return ConnectionStatusDTO(
            provider=status.provider,
            name=status.name,
            connected=status.connected,
            read_only_scope=status.read_only_scope,
            domain_tag=status.domain_tag,
            list_wired=status.list_wired,
        )

    return ConnectionsStatusDTO(
        calendar=_one(view.calendar),
        others=[_one(o) for o in view.others],
    )


class ConnectSessionDTO(BaseModel):
    """A connect session the page opens to run the provider OAuth flow (D160)."""

    provider_config_key: str
    connect_url: str | None = None
    session_token: str | None = None


class ConnectCallbackRequest(BaseModel):
    """The connect callback: the provider connection reference the flow issued."""

    provider_connection_ref: str


class StoredConnectionDTO(BaseModel):
    """The stored connection + first-sync state."""

    connection_id: str
    synced: bool
    sync_error: str | None = None


__all__ = [
    "ConnectCallbackRequest",
    "ConnectSessionDTO",
    "ConnectionStatusDTO",
    "ConnectionsStatusDTO",
    "StoredConnectionDTO",
    "connections_view_to_dto",
]
