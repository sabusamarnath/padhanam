"""ConnectionRepository port — connection identity plus sync-token state (D148).

The Connection value object is identity (the opaque provider references);
the sync token is per-connection sync *state* the pipeline reads before an
incremental pull and writes after each sync run. Kept off the Connection
value object (which stays identity-only) and accessed through dedicated
methods so connection identity and mutable sync state do not conflate.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from contexts.calendar.domain.connection import Connection
from shared_kernel.tenant_context import TenantContext


class ConnectionRepository(Protocol):
    async def save_connection(
        self, *, tenant_context: TenantContext, connection: Connection
    ) -> None:
        """Insert or update a connection on (tenant_id, provider, config key)."""
        ...

    async def get_connection(
        self, *, tenant_context: TenantContext, connection_id: UUID
    ) -> Connection | None:
        """Return the connection by id, or None."""
        ...

    async def get_sync_token(
        self, *, tenant_context: TenantContext, connection_id: UUID
    ) -> str | None:
        """Return the stored sync token for the connection, or None."""
        ...

    async def set_sync_token(
        self,
        *,
        tenant_context: TenantContext,
        connection_id: UUID,
        sync_token: str | None,
    ) -> None:
        """Persist the next sync token (or clear it on full-resync)."""
        ...
