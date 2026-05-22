"""Composition wiring for the messaging surface (D129, S45).

Carries the messaging composition in one ``MessagingComposition``
bundle plus the builders the composition root invokes:

- ``MessageRepositoryAdapter`` implements the messaging context's
  ``MessageRepository`` port by routing each call to a freshly-built
  ``PostgresMessageRepository`` bound to the request's tenant —
  mirroring the S44b ``IntakeRepositoryAdapter`` shape.

- ``MessageWriterAdapter`` implements the intake context's
  consumer-defined ``MessageWriter`` port (D127 alternative (d)).
  It is the legal cross-context seam: ``apps/`` may import
  ``contexts.messaging.application`` directly, so this adapter
  invokes the messaging ``record_inbound_message`` use case and
  translates its Message aggregate into the intake-owned
  ``MessageWriteResult`` DTO.

- The outbound ``MessageDeliveryPort`` is selected by the
  ``MESSAGING_ADAPTER`` setting — ``local_echo`` (the default) or
  ``twilio``. The delivery adapter is a single platform-wide
  instance, not per-tenant.

Lands in this module rather than ``apps/api/_agent_runtime_wiring.py``
because that file is already past its 600-line split trigger, per
the S44b ``_intake_wiring.py`` precedent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from uuid import UUID

from contexts.audit.domain.ports import AuditPort

from contexts.intake.application.ports.message_writer import (
    MessageWriteResult,
)
from contexts.messaging.adapters.outbound.postgres.message_repository import (
    PostgresMessageRepository,
)
from contexts.messaging.application.record_inbound_message import (
    record_inbound_message as record_inbound_message_use_case,
)
from contexts.messaging.domain import Message, MessageChannel
from contexts.messaging.domain.query_filters import (
    MessageListCursor,
    MessageListFilters,
)
from contexts.messaging.ports.message_delivery_port import MessageDeliveryPort
from contexts.messaging.ports.message_repository import MessageListPage
from contexts.tenancy.adapters.outbound.postgres.registry import (
    PostgresTenantRegistry,
)
from contexts.tenancy.application.connection_resolution import (
    TenantSessionFactoryCache,
)
from padhanam.config import MessagingAdapter, MessagingSettings
from padhanam.observability.security_events import SecurityEventLogger
from padhanam.security import Principal
from shared_kernel import ActorContext, TenantContext, TenantId

_SessionFactoryForTenant = Callable[[TenantContext], Awaitable[Any]]


def _message_write_result(message: Message) -> MessageWriteResult:
    """Translate a messaging Message into the intake-owned write result."""
    assert message.intake_id is not None, (
        "an inbound Message recorded via the orchestration carries an "
        "intake_id per D128"
    )
    return MessageWriteResult(
        message_id=message.id,
        direction=message.direction.value,
        channel=message.channel.value,
        body=message.body,
        from_address=message.from_address,
        to_address=message.to_address,
        status=message.status.value,
        external_id=message.external_id,
        intake_id=message.intake_id,
        created_at=message.created_at,
    )


class MessageRepositoryAdapter:
    """Per-request-tenant-resolving wiring for the MessageRepository port."""

    def __init__(
        self, *, session_factory_for_tenant: _SessionFactoryForTenant
    ) -> None:
        self._session_factory_for_tenant = session_factory_for_tenant

    async def _build(
        self, tenant_context: TenantContext
    ) -> PostgresMessageRepository:
        sessionmaker = await self._session_factory_for_tenant(tenant_context)

        async def _resolver(_tid: TenantId) -> object:
            return sessionmaker

        return PostgresMessageRepository(
            per_tenant_sessionmaker_resolver=_resolver,
            bound_tenant_id=TenantId(str(tenant_context.tenant_id)),
        )

    async def save(
        self, *, tenant_context: TenantContext, message: Message
    ) -> None:
        repo = await self._build(tenant_context)
        await repo.save(tenant_context=tenant_context, message=message)

    async def get_by_id(
        self, *, tenant_context: TenantContext, message_id: UUID
    ) -> Message | None:
        repo = await self._build(tenant_context)
        return await repo.get_by_id(
            tenant_context=tenant_context, message_id=message_id
        )

    async def list_for_tenant(
        self,
        *,
        tenant_context: TenantContext,
        filters: MessageListFilters | None,
        cursor: MessageListCursor | None,
        page_size: int,
    ) -> MessageListPage:
        repo = await self._build(tenant_context)
        return await repo.list_for_tenant(
            tenant_context=tenant_context,
            filters=filters,
            cursor=cursor,
            page_size=page_size,
        )


class MessageWriterAdapter:
    """apps/ adapter implementing the intake context's MessageWriter port.

    The legal cross-context seam (D127 alternative (d)): invokes the
    messaging ``record_inbound_message`` use case and translates its
    Message aggregate into the intake-owned ``MessageWriteResult``.
    """

    def __init__(
        self,
        *,
        session_factory_for_tenant: _SessionFactoryForTenant,
        audit_port: AuditPort,
    ) -> None:
        self._session_factory_for_tenant = session_factory_for_tenant
        self._audit_port = audit_port

    async def _repo(
        self, tenant_context: TenantContext
    ) -> PostgresMessageRepository:
        sessionmaker = await self._session_factory_for_tenant(tenant_context)

        async def _resolver(_tid: TenantId) -> object:
            return sessionmaker

        return PostgresMessageRepository(
            per_tenant_sessionmaker_resolver=_resolver,
            bound_tenant_id=TenantId(str(tenant_context.tenant_id)),
        )

    async def record_inbound_message(
        self,
        *,
        actor: ActorContext,
        channel: str,
        from_address: str,
        to_address: str,
        body: str,
        external_id: str | None,
        intake_id: UUID,
    ) -> MessageWriteResult:
        repository = await self._repo(actor.tenant_context)
        message = await record_inbound_message_use_case(
            repository=repository,
            audit_port=self._audit_port,
            actor=actor,
            channel=MessageChannel(channel),
            from_address=from_address,
            to_address=to_address,
            body=body,
            external_id=external_id,
            intake_id=intake_id,
        )
        return _message_write_result(message)


@dataclass(frozen=True)
class MessagingComposition:
    """The messaging composition seam exposed on ``app.state.messaging``.

    Bundles the repository adapter, the selected delivery adapter, the
    MessageWriter consumer-port adapter, and the configuration the
    routes need (the platform sender address and the inbound-webhook
    settings).
    """

    repository: MessageRepositoryAdapter
    delivery_port: MessageDeliveryPort
    message_writer: MessageWriterAdapter
    from_address: str
    webhook_tenant_id: str
    webhook_jurisdiction: str
    webhook_url: str
    twilio_auth_token: str


def _select_delivery_adapter(
    settings: MessagingSettings,
) -> MessageDeliveryPort:
    """Select the outbound delivery adapter per ``MESSAGING_ADAPTER``.

    The adapter modules are imported lazily so the default
    (``local_echo``) path never imports the twilio SDK.
    """
    if settings.messaging_adapter is MessagingAdapter.TWILIO:
        from contexts.messaging.adapters.outbound.twilio.twilio_message_delivery import (  # noqa: E501
            TwilioMessageDeliveryAdapter,
        )

        return TwilioMessageDeliveryAdapter(
            account_sid=settings.twilio_account_sid,
            auth_token=settings.twilio_auth_token,
        )
    from contexts.messaging.adapters.outbound.local_echo.local_echo_message_delivery import (  # noqa: E501
        LocalEchoMessageDeliveryAdapter,
    )

    return LocalEchoMessageDeliveryAdapter()


def _session_factory_for_tenant_builder(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
) -> _SessionFactoryForTenant:
    async def _session_factory_for_tenant(
        tenant_context: TenantContext,
    ) -> Any:
        return await session_factory_cache.get(
            tenant_id=TenantId(str(tenant_context.tenant_id)),
            principal=operator_principal,
            registry=tenant_registry,
            security_events=security_events,
        )

    return _session_factory_for_tenant


def build_messaging_composition(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
    audit_port: AuditPort,
) -> MessagingComposition:
    """Wire the messaging composition for the production app (D129)."""
    settings = MessagingSettings()
    session_factory_for_tenant = _session_factory_for_tenant_builder(
        tenant_registry=tenant_registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=security_events,
    )
    return MessagingComposition(
        repository=MessageRepositoryAdapter(
            session_factory_for_tenant=session_factory_for_tenant,
        ),
        delivery_port=_select_delivery_adapter(settings),
        message_writer=MessageWriterAdapter(
            session_factory_for_tenant=session_factory_for_tenant,
            audit_port=audit_port,
        ),
        from_address=settings.twilio_whatsapp_from,
        webhook_tenant_id=settings.webhook_tenant_id,
        webhook_jurisdiction=settings.webhook_jurisdiction,
        webhook_url=settings.webhook_url,
        twilio_auth_token=settings.twilio_auth_token,
    )


__all__ = [
    "MessageRepositoryAdapter",
    "MessageWriterAdapter",
    "MessagingComposition",
    "build_messaging_composition",
]
