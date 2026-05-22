"""Repository port for the messaging context (D129).

A single port carries the Message aggregate's write and read
surfaces — ``save``, ``get_by_id``, ``list_for_tenant`` — mirroring
the intake repository shape. The budget-table split trigger (a
distinct reader port) does not fire at S45: the messaging surface
is small and the read and write shapes share the Message aggregate.

Tenant scoping flows through ``TenantContext``; cross-tenant reads
return ``None`` / empty per the tenant-isolation contract.

Ports layer is pure per D16 — no SQLAlchemy, no asyncpg.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from contexts.messaging.domain import Message
from contexts.messaging.domain.query_filters import (
    MessageListCursor,
    MessageListFilters,
)
from shared_kernel import TenantContext


@dataclass(frozen=True)
class MessageListPage:
    """One page of ``list_messages`` output."""

    messages: tuple[Message, ...]
    next_cursor: MessageListCursor | None


class MessageRepository(Protocol):
    """Write-plus-read port for the Message aggregate."""

    async def save(
        self, *, tenant_context: TenantContext, message: Message
    ) -> None:
        """Persist a new Message. Messages are immutable once recorded."""
        ...

    async def get_by_id(
        self, *, tenant_context: TenantContext, message_id: UUID
    ) -> Message | None:
        """Return the Message, or None when absent or cross-tenant."""
        ...

    async def list_for_tenant(
        self,
        *,
        tenant_context: TenantContext,
        filters: MessageListFilters | None,
        cursor: MessageListCursor | None,
        page_size: int,
    ) -> MessageListPage:
        """List a tenant's messages, paginated on ``(created_at DESC, id DESC)``."""
        ...


__all__ = ["MessageListPage", "MessageRepository"]
