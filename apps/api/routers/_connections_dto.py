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


__all__ = [
    "ConnectionStatusDTO",
    "ConnectionsStatusDTO",
    "connections_view_to_dto",
]
