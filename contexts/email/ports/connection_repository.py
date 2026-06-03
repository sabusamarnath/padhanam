"""ConnectionRepository port — email connection identity + history anchor (D151).

Mirrors calendar's ConnectionRepository. The Connection value object is
identity (opaque provider references); the mailbox ``history_id`` (from
``getProfile``) is the per-connection dormant incremental anchor, stored
through dedicated get/set methods so identity and the anchor do not
conflate. No incremental path consumes the anchor this phase.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from contexts.email.domain.connection import Connection
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

    async def get_history_id(
        self, *, tenant_context: TenantContext, connection_id: UUID
    ) -> str | None:
        """Return the stored mailbox history anchor, or None (dormant, D151)."""
        ...

    async def set_history_id(
        self,
        *,
        tenant_context: TenantContext,
        connection_id: UUID,
        history_id: str | None,
    ) -> None:
        """Persist the mailbox history anchor (the dormant incremental seed)."""
        ...
