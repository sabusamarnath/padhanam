"""In-memory fakes for messaging application-layer unit tests (S45, S53)."""

from __future__ import annotations

from uuid import UUID

from contexts.audit.domain.events import AuditEvent

from contexts.messaging.domain import Message, MessageChannel, MessageStatus
from contexts.messaging.domain.channel_destination import ChannelDestination
from contexts.messaging.domain.channel_type import ChannelType
from contexts.messaging.domain.query_filters import (
    MessageListCursor,
    MessageListFilters,
)
from contexts.messaging.ports.message_delivery_port import DeliveryResult
from contexts.messaging.ports.message_repository import MessageListPage
from shared_kernel import TenantContext
from shared_kernel.message_intent import MessageIntent


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


class FakeFiredTriggersRepository:
    """In-memory FiredTriggersRepository simulating the four-tuple UNIQUE (D147).

    ``insert_or_skip`` returns True on a fresh four-tuple and False on
    a duplicate, mirroring the Postgres ON CONFLICT DO NOTHING
    semantics. A ``None`` idempotency_key is treated as a distinct
    key per insertion (mirroring Postgres NULL semantics where
    multiple NULL rows are permitted) — each MANUAL trigger inserts
    fresh. The ``inserted`` list records every successful insertion
    keyed by tenant for tenant-isolation assertions.
    """

    def __init__(self) -> None:
        self._seen: set[tuple[str, str, str, str]] = set()
        self.inserted: list[tuple[str, str, str, str | None]] = []
        self._null_counter = 0

    async def insert_or_skip(
        self,
        *,
        tenant_context: TenantContext,
        user_id: str,
        trigger_type: str,
        idempotency_key: str | None,
    ) -> bool:
        if idempotency_key is None:
            # Postgres permits multiple NULL rows under a UNIQUE
            # constraint; each null-keyed insert is fresh.
            self._null_counter += 1
            self.inserted.append(
                (str(tenant_context.tenant_id), user_id, trigger_type, None)
            )
            return True
        key = (
            str(tenant_context.tenant_id),
            user_id,
            trigger_type,
            idempotency_key,
        )
        if key in self._seen:
            return False
        self._seen.add(key)
        self.inserted.append(
            (str(tenant_context.tenant_id), user_id, trigger_type, idempotency_key)
        )
        return True


class FakeChannelResolver:
    """Returns the configured destination; records resolution requests.

    Phase 2-A ChannelResolver Protocol fake for messaging application-
    layer unit tests (S53). Tests can inspect ``resolve_calls`` to
    verify the use case consults the resolver before delivery.
    """

    def __init__(
        self,
        *,
        channel_type: ChannelType = ChannelType.WHATSAPP,
        channel_address: str = "+15551234567",
    ) -> None:
        self._destination = ChannelDestination(
            channel_type=channel_type,
            channel_address=channel_address,
        )
        self.resolve_calls: list[dict[str, object]] = []

    async def resolve_channel(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        message_intent: MessageIntent,
    ) -> ChannelDestination:
        self.resolve_calls.append(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "message_intent": message_intent,
            }
        )
        return self._destination
