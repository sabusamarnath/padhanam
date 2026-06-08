"""ConnectionRepository port for the tasks context (D167).

Mirrors calendar/email: save (idempotent on tenant+provider+config-key) and
fetch the tenant's task-provider connection. No sync-token/history-id anchor —
Google Tasks re-pulls fully each refresh (the simplest D155 model; no
incremental at this phase).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from contexts.tasks.domain.connection import Connection
from shared_kernel import TenantContext


class ConnectionRepository(Protocol):
    async def save_connection(
        self, *, tenant_context: TenantContext, connection: Connection
    ) -> None:
        ...

    async def get_connection(
        self, *, tenant_context: TenantContext, connection_id: UUID
    ) -> Connection | None:
        ...


__all__ = ["ConnectionRepository"]
