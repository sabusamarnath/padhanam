"""Composition wiring for the daily-briefing DailyBriefingReader (D146, S54).

The legal cross-context seam (D17): ``apps/`` may import producer-
context application modules directly, so this adapter implements
daily-briefing's ``DailyBriefingReader`` consumer port by composing
three producer contexts:

- ``read_intake_records`` -> the intake context's
  ``IntakeRepository.list_for_tenant`` (paginated on created_at DESC;
  trimmed to the window in-memory per S54 pre-write reconciliation
  Finding 2 — IntakeListFilters has no time-window dimension at
  Phase 2-A dogfooding scale).
- ``read_audit_events`` -> the audit context's
  ``AuditEventReader.list_audit_events_with_filters`` with a
  ``timestamp_range`` filter (the audit filters DO carry a time
  window, so the window applies at the query rather than in-memory).
- ``read_active_cases`` -> the portfolio context's ``list_cases`` use
  case (current-state snapshot; no window).

Lands in its own module mirroring the
``apps/api/_mirror_portfolio_wiring.py`` precedent: a per-context
wiring file keeps each cross-context seam grep-able.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Awaitable, Callable
from uuid import UUID

from contexts.audit.domain.destination import AuditDestination
from contexts.audit.domain.ports import AuditPort
from contexts.audit.domain.query_filters import AuditEventListFilters
from contexts.audit.ports.reader import AuditEventReader
from contexts.daily_briefing.application.daily_briefing_implementer import (
    DailyBriefingImplementer,
)
from contexts.daily_briefing.application.ports.daily_briefing_composer import (
    DailyBriefingComposer,
)
from contexts.daily_briefing.application.ports.daily_briefing_reader import (
    DailyBriefingAuditEvent,
    DailyBriefingCase,
    DailyBriefingIntakeRecord,
    DailyBriefingReader,
)
from contexts.intake.domain import ManualEntryPayload
from contexts.intake.ports.intake_repository import IntakeRepository
from contexts.messaging.application.ports.channel_resolver import (
    ChannelResolver,
)
from contexts.messaging.application.send_message import send_message
from contexts.messaging.domain import MessageChannel
from contexts.messaging.domain.channel_type import ChannelType
from contexts.messaging.ports.message_delivery_port import MessageDeliveryPort
from contexts.messaging.ports.message_repository import MessageRepository
from contexts.portfolio.adapters.outbound.postgres.portfolio_reader import (
    PostgresPortfolioReader,
)
from contexts.portfolio.application.list_cases import list_cases
from contexts.tenancy.adapters.outbound.postgres.registry import (
    PostgresTenantRegistry,
)
from contexts.tenancy.application.connection_resolution import (
    TenantSessionFactoryCache,
)
from padhanam.observability.security_events import SecurityEventLogger
from padhanam.security import Principal
from shared_kernel import ActorContext, TenantContext, TenantId
from shared_kernel.message_intent import MessageIntent

_SessionFactoryForTenant = Callable[[TenantContext], Awaitable[Any]]

_PER_TENANT: AuditDestination = "per_tenant"

# Dogfooding scale: a single page covers the window's intake records
# and the active-case listing without paginating. Phase 2-B+ may swap
# to true pagination (or a dedicated created_at_after intake filter)
# when tenant volume outgrows the single page.
_INTAKE_SCAN_PAGE_SIZE = 200
_AUDIT_PAGE_SIZE = 200
_CASE_PAGE_SIZE = 200


def _intake_summary(payload: object) -> str:
    """Project an IntakePayload into a short summary for the briefing."""
    if isinstance(payload, ManualEntryPayload):
        text = payload.raw_text.strip()
        return text[:200]
    return ""


class DailyBriefingReaderAdapter:
    """apps/ adapter implementing daily-briefing's DailyBriefingReader (D146)."""

    def __init__(
        self,
        *,
        session_factory_for_tenant: _SessionFactoryForTenant,
        intake_repository: IntakeRepository,
        audit_event_reader: AuditEventReader,
    ) -> None:
        self._session_factory_for_tenant = session_factory_for_tenant
        self._intake_repository = intake_repository
        self._audit_event_reader = audit_event_reader

    async def _portfolio_reader(
        self, tenant_context: TenantContext
    ) -> PostgresPortfolioReader:
        sessionmaker = await self._session_factory_for_tenant(tenant_context)

        async def _resolver(_tid: TenantId) -> object:
            return sessionmaker

        return PostgresPortfolioReader(
            per_tenant_sessionmaker_resolver=_resolver,
            bound_tenant_id=TenantId(str(tenant_context.tenant_id)),
        )

    async def read_intake_records(
        self,
        *,
        actor: ActorContext,
        window: tuple[datetime, datetime],
    ) -> tuple[DailyBriefingIntakeRecord, ...]:
        start, end = window
        page = await self._intake_repository.list_for_tenant(
            tenant_context=actor.tenant_context,
            filters=None,
            cursor=None,
            page_size=_INTAKE_SCAN_PAGE_SIZE,
        )
        records: list[DailyBriefingIntakeRecord] = []
        for intake in page.intakes:
            if start <= intake.created_at <= end:
                records.append(
                    DailyBriefingIntakeRecord(
                        intake_id=intake.id,
                        intake_source=intake.intake_source.value,
                        summary=_intake_summary(intake.payload),
                        created_at=intake.created_at,
                    )
                )
        return tuple(records)

    async def read_audit_events(
        self,
        *,
        actor: ActorContext,
        window: tuple[datetime, datetime],
    ) -> tuple[DailyBriefingAuditEvent, ...]:
        filters = AuditEventListFilters(timestamp_range=window)
        page = await self._audit_event_reader.list_audit_events_with_filters(
            destination=_PER_TENANT,
            filters=filters,
            cursor=None,
            page_size=_AUDIT_PAGE_SIZE,
            tenant_context=actor.tenant_context,
        )
        return tuple(
            DailyBriefingAuditEvent(
                event_id=event.id,
                action_verb=event.action_verb,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                timestamp=event.timestamp,
            )
            for event in page.events
        )

    async def read_active_cases(
        self, *, actor: ActorContext
    ) -> tuple[DailyBriefingCase, ...]:
        reader = await self._portfolio_reader(actor.tenant_context)
        page = await list_cases(
            reader=reader, actor=actor, page_size=_CASE_PAGE_SIZE
        )
        return tuple(
            DailyBriefingCase(
                case_id=case.id,
                title=case.title,
                status=case.status.value,
                created_at=case.created_at,
            )
            for case in page.cases
        )


def build_daily_briefing_reader(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
    intake_repository: IntakeRepository,
    audit_event_reader: AuditEventReader,
) -> DailyBriefingReaderAdapter:
    """Wire the daily-briefing DailyBriefingReader adapter (D146)."""

    async def _session_factory_for_tenant(
        tenant_context: TenantContext,
    ) -> Any:
        return await session_factory_cache.get(
            tenant_id=TenantId(str(tenant_context.tenant_id)),
            principal=operator_principal,
            registry=tenant_registry,
            security_events=security_events,
        )

    return DailyBriefingReaderAdapter(
        session_factory_for_tenant=_session_factory_for_tenant,
        intake_repository=intake_repository,
        audit_event_reader=audit_event_reader,
    )


_CHANNEL_TYPE_TO_MESSAGE_CHANNEL = {
    ChannelType.WHATSAPP: MessageChannel.WHATSAPP,
}


class BriefingNotifierAdapter:
    """apps/ adapter implementing daily-briefing's BriefingNotifier port (D146).

    The legal cross-context seam (D17): ``apps/`` may import
    ``contexts.messaging.application`` directly, so this adapter
    resolves the operator's channel destination via the ChannelResolver
    (D144) and invokes the messaging ``send_message`` use case with
    ``message_intent=BROADCAST_DAILY_BRIEFING``. send_message owns
    delivery, persistence, and the outbound audit event.
    """

    def __init__(
        self,
        *,
        repository: MessageRepository,
        delivery_port: MessageDeliveryPort,
        audit_port: AuditPort,
        channel_resolver: ChannelResolver,
        from_address: str,
    ) -> None:
        self._repository = repository
        self._delivery_port = delivery_port
        self._audit_port = audit_port
        self._channel_resolver = channel_resolver
        self._from_address = from_address

    async def send_briefing(self, *, actor: ActorContext, body: str) -> None:
        destination = await self._channel_resolver.resolve_channel(
            tenant_id=UUID(str(actor.tenant_context.tenant_id)),
            user_id=actor.actor_id,
            message_intent=MessageIntent.BROADCAST_DAILY_BRIEFING,
        )
        channel = _CHANNEL_TYPE_TO_MESSAGE_CHANNEL.get(
            destination.channel_type, MessageChannel.WHATSAPP
        )
        await send_message(
            repository=self._repository,
            delivery_port=self._delivery_port,
            audit_port=self._audit_port,
            channel_resolver=self._channel_resolver,
            actor=actor,
            from_address=self._from_address,
            to_address=destination.channel_address,
            body=body,
            channel=channel,
            message_intent=MessageIntent.BROADCAST_DAILY_BRIEFING,
        )


def build_daily_briefing_implementer(
    *,
    reader: DailyBriefingReader,
    composer: DailyBriefingComposer,
    notifier: BriefingNotifierAdapter,
    jurisdiction: str,
    window_hours: int,
) -> DailyBriefingImplementer:
    """Wire the daily-briefing BroadcastFlow implementer (D142, D146)."""
    return DailyBriefingImplementer(
        reader=reader,
        composer=composer,
        notifier=notifier,
        jurisdiction=jurisdiction,
        window_hours=window_hours,
    )


__all__ = [
    "BriefingNotifierAdapter",
    "DailyBriefingReaderAdapter",
    "build_daily_briefing_implementer",
    "build_daily_briefing_reader",
]
