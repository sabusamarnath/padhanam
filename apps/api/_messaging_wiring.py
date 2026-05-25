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

from apps.api.adapters.cell_dispatch_inprocess import (
    InProcessCellDispatchAdapter,
)
from apps.api._portfolio_gateway_wiring import (
    PortfolioGatewayAdapter,
    build_portfolio_gateway,
)
from contexts.audit.domain.ports import AuditPort

from contexts.intake.application.ports.message_writer import (
    MessageWriteResult,
)
from contexts.inference.adapters.confidence_self_reported import (
    SelfReportedConfidenceAdapter,
)
from contexts.messaging.adapters.threshold_single_pair import (
    SinglePairThresholdResolverAdapter,
)
from contexts.messaging.application.ports.cell_dispatch import CellDispatch
from contexts.messaging.application.ports.pending_clarification_reader import (
    PendingClarificationReader,
)
from contexts.messaging.adapters.outbound.postgres.message_repository import (
    PostgresMessageRepository,
)
from contexts.messaging.adapters.outbound.postgres.pending_clarification_repository import (  # noqa: E501
    PostgresPendingClarificationRepository,
)
from contexts.messaging.application.record_inbound_message import (
    record_inbound_message as record_inbound_message_use_case,
)
from contexts.messaging.domain import Message, MessageChannel
from contexts.messaging.domain.pending_clarification import (
    PendingClarification,
)
from contexts.messaging.domain.query_filters import (
    MessageListCursor,
    MessageListFilters,
)
from contexts.messaging.ports.message_delivery_port import MessageDeliveryPort
from contexts.messaging.ports.message_repository import MessageListPage
from contexts.messaging.ports.pending_clarification_repository import (
    PendingClarificationRepository,
)
from contexts.tenancy.adapters.outbound.postgres.registry import (
    PostgresTenantRegistry,
)
from contexts.tenancy.application.connection_resolution import (
    TenantSessionFactoryCache,
)
from padhanam.config import MessagingAdapter, MessagingSettings
from padhanam.observability.security_events import SecurityEventLogger
from padhanam.security import Principal
from shared_kernel import (
    ActorContext,
    ConfidenceCalculator,
    ConfidenceThresholds,
    StructuredOutputPort,
    TenantContext,
    TenantId,
    ThresholdResolver,
)

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


class PendingClarificationRepositoryAdapter:
    """Per-request-tenant-resolving wiring for PendingClarificationRepository."""

    def __init__(
        self, *, session_factory_for_tenant: _SessionFactoryForTenant
    ) -> None:
        self._session_factory_for_tenant = session_factory_for_tenant

    async def _build(
        self, tenant_context: TenantContext
    ) -> PostgresPendingClarificationRepository:
        sessionmaker = await self._session_factory_for_tenant(tenant_context)

        async def _resolver(_tid: TenantId) -> object:
            return sessionmaker

        return PostgresPendingClarificationRepository(
            per_tenant_sessionmaker_resolver=_resolver,
            bound_tenant_id=TenantId(str(tenant_context.tenant_id)),
        )

    async def save(
        self,
        *,
        tenant_context: TenantContext,
        pending: PendingClarification,
    ) -> None:
        repo = await self._build(tenant_context)
        await repo.save(tenant_context=tenant_context, pending=pending)

    async def update_status(
        self,
        *,
        tenant_context: TenantContext,
        pending: PendingClarification,
    ) -> None:
        repo = await self._build(tenant_context)
        await repo.update_status(
            tenant_context=tenant_context, pending=pending
        )

    async def get_by_id(
        self,
        *,
        tenant_context: TenantContext,
        pending_id: UUID,
    ) -> PendingClarification | None:
        repo = await self._build(tenant_context)
        return await repo.get_by_id(
            tenant_context=tenant_context, pending_id=pending_id
        )

    async def get_active_for_user(
        self,
        *,
        tenant_context: TenantContext,
        user_id: str,
    ) -> PendingClarification | None:
        repo = await self._build(tenant_context)
        return await repo.get_active_for_user(
            tenant_context=tenant_context, user_id=user_id
        )


class PendingClarificationReaderAdapter:
    """Cell-facing read adapter wrapping the repository at composition root."""

    def __init__(
        self,
        *,
        repository: PendingClarificationRepository,
        webhook_tenant_id: str,
        webhook_jurisdiction: str,
    ) -> None:
        self._repository = repository
        self._tenant_id = webhook_tenant_id
        self._jurisdiction = webhook_jurisdiction

    async def get_active(
        self, *, tenant_id: UUID, user_id: str
    ) -> PendingClarification | None:
        tenant_context = TenantContext(
            tenant_id=str(tenant_id),
            jurisdiction=self._jurisdiction,
            cost_attribution_id=str(tenant_id),
        )
        return await self._repository.get_active_for_user(
            tenant_context=tenant_context, user_id=user_id
        )


@dataclass(frozen=True)
class MessagingComposition:
    """The messaging composition seam exposed on ``app.state.messaging``.

    Bundles the repository adapter, the selected delivery adapter, the
    MessageWriter consumer-port adapter, the manual entry cell's
    collaborators (the PortfolioGateway adapter and the
    StructuredOutputPort, S46), and the configuration the routes need
    (the platform sender address and the inbound-webhook settings).
    """

    repository: MessageRepositoryAdapter
    delivery_port: MessageDeliveryPort
    message_writer: MessageWriterAdapter
    portfolio_gateway: PortfolioGatewayAdapter
    structured_output_port: StructuredOutputPort
    confidence_calculator: ConfidenceCalculator
    cell_dispatch: CellDispatch
    pending_clarification_repository: PendingClarificationRepository
    pending_clarification_reader: PendingClarificationReader
    threshold_resolver: ThresholdResolver
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
    structured_output_port: StructuredOutputPort,
) -> MessagingComposition:
    """Wire the messaging composition for the production app (D129, S46).

    ``structured_output_port`` is the inference LiteLLM adapter (which
    implements StructuredOutputPort) — the manual entry cell's
    intent-extraction collaborator. The PortfolioGateway adapter is
    wired here from the shared per-tenant connection plumbing.
    """
    settings = MessagingSettings()
    session_factory_for_tenant = _session_factory_for_tenant_builder(
        tenant_registry=tenant_registry,
        session_factory_cache=session_factory_cache,
        operator_principal=operator_principal,
        security_events=security_events,
    )
    pending_clarification_repository = PendingClarificationRepositoryAdapter(
        session_factory_for_tenant=session_factory_for_tenant,
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
        portfolio_gateway=build_portfolio_gateway(
            tenant_registry=tenant_registry,
            session_factory_cache=session_factory_cache,
            operator_principal=operator_principal,
            security_events=security_events,
            audit_port=audit_port,
        ),
        structured_output_port=structured_output_port,
        confidence_calculator=SelfReportedConfidenceAdapter(),
        cell_dispatch=InProcessCellDispatchAdapter(),
        pending_clarification_repository=pending_clarification_repository,
        pending_clarification_reader=PendingClarificationReaderAdapter(
            repository=pending_clarification_repository,
            webhook_tenant_id=settings.webhook_tenant_id,
            webhook_jurisdiction=settings.webhook_jurisdiction,
        ),
        threshold_resolver=SinglePairThresholdResolverAdapter(
            thresholds=ConfidenceThresholds(
                high=settings.confidence_high_cutoff,
                medium=settings.confidence_medium_cutoff,
            ),
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
    "PendingClarificationReaderAdapter",
    "PendingClarificationRepositoryAdapter",
    "build_messaging_composition",
]
