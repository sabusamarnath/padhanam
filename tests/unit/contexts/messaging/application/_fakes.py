"""In-memory fakes for messaging application-layer unit tests (S45)."""

from __future__ import annotations

from uuid import UUID

from contexts.audit.domain.events import AuditEvent

from contexts.messaging.domain import Message, MessageChannel, MessageStatus
from contexts.messaging.domain.query_filters import (
    MessageListCursor,
    MessageListFilters,
)
from contexts.messaging.ports.message_delivery_port import DeliveryResult
from contexts.messaging.ports.message_repository import MessageListPage
from shared_kernel import TenantContext


class FakeAuditPort:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def emit(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        return event


class FakeMessageRepository:
    def __init__(self) -> None:
        self.messages: dict[UUID, Message] = {}

    async def save(
        self, *, tenant_context: TenantContext, message: Message
    ) -> None:
        self.messages[message.id] = message

    async def get_by_id(
        self, *, tenant_context: TenantContext, message_id: UUID
    ) -> Message | None:
        return self.messages.get(message_id)

    async def list_for_tenant(
        self,
        *,
        tenant_context: TenantContext,
        filters: MessageListFilters | None,
        cursor: MessageListCursor | None,
        page_size: int,
    ) -> MessageListPage:
        rows = sorted(
            self.messages.values(),
            key=lambda m: (m.created_at, str(m.id)),
            reverse=True,
        )
        if filters is not None and filters.directions is not None:
            rows = [m for m in rows if m.direction in filters.directions]
        if filters is not None and filters.channels is not None:
            rows = [m for m in rows if m.channel in filters.channels]
        return MessageListPage(
            messages=tuple(rows[:page_size]), next_cursor=None
        )


class FakeMessageDeliveryPort:
    """Records send calls; returns a configurable DeliveryResult."""

    def __init__(
        self,
        *,
        status: MessageStatus = MessageStatus.SENT,
        external_id: str | None = "SMfake0001",
    ) -> None:
        self._status = status
        self._external_id = external_id
        self.send_calls: list[dict[str, str]] = []

    async def send(
        self,
        *,
        channel: MessageChannel,
        from_address: str,
        to_address: str,
        body: str,
    ) -> DeliveryResult:
        self.send_calls.append(
            {
                "channel": channel.value,
                "from_address": from_address,
                "to_address": to_address,
                "body": body,
            }
        )
        return DeliveryResult(
            external_id=self._external_id, status=self._status
        )
