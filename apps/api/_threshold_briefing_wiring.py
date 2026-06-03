"""Threshold-briefing wiring adapters (D146, D147, D153, S57).

The legal cross-context seam (D17): ``apps/`` may import producer-context
application modules, so these adapters implement the threshold context's
consumer ports against calendar (state read, refresh), messaging (emit,
notify), and the inference LLM (compose, wired in main.py). The threshold
context itself imports none of them — it consumes the ports.

Four adapters:

- ``CalendarStateReaderAdapter`` — over the calendar PostgresMeetingStore;
  maps calendar ``Meeting`` → threshold ``MeetingState``.
- ``ActiveRuleRefreshAdapter`` — wraps the calendar refresh adapter
  (D149 ``sync_calendar`` scoped full pull); maps its failure to
  ``ActiveRuleRefreshError``.
- ``ThresholdCrossedEmitterAdapter`` — builds the THRESHOLD_CROSSED
  TriggerContext from a crossing and fires it through the D147 FireTrigger
  flow (idempotency keyed on the crossing identity, then dispatch to the
  threshold-briefing implementer).
- ``ThresholdNotifierAdapter`` — resolves the operator channel (D144) and
  invokes ``send_message`` with ``BROADCAST_THRESHOLD_BRIEFING``.
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from contexts.audit.domain.ports import AuditPort
from contexts.calendar.adapters.outbound.postgres.meeting_store import (
    PostgresMeetingStore,
)
from contexts.messaging.application.fire_trigger import fire_trigger
from contexts.messaging.application.ports.broadcast_dispatch import (
    BroadcastDispatch,
)
from contexts.messaging.application.ports.channel_resolver import (
    ChannelResolver,
)
from contexts.messaging.application.send_message import send_message
from contexts.messaging.domain import MessageChannel
from contexts.messaging.domain.channel_type import ChannelType
from contexts.messaging.ports.fired_triggers_repository import (
    FiredTriggersRepository,
)
from contexts.messaging.ports.message_delivery_port import MessageDeliveryPort
from contexts.messaging.ports.message_repository import MessageRepository
from contexts.threshold_briefing.application.ports.active_rule_refresh import (
    ActiveRuleRefreshError,
)
from contexts.threshold_briefing.application.ports.calendar_state_reader import (
    MeetingState,
)
from contexts.threshold_briefing.domain.rule_match import RuleMatch
from shared_kernel import ActorContext, TenantContext, TenantId
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles
from shared_kernel.broadcast_flow import BroadcastTriggerType, TriggerContext
from shared_kernel.message_intent import MessageIntent

_logger = logging.getLogger("padhanam.threshold_briefing.wiring")

_CHANNEL_TYPE_TO_MESSAGE_CHANNEL = {
    ChannelType.WHATSAPP: MessageChannel.WHATSAPP,
}


class CalendarStateReaderAdapter:
    """Implements CalendarStateReader over the calendar meetings store (D153)."""

    def __init__(self, *, meeting_reader: PostgresMeetingStore) -> None:
        self._meeting_reader = meeting_reader

    async def list_meetings(
        self, *, actor: ActorContext, include_cancelled: bool = True
    ) -> tuple[MeetingState, ...]:
        meetings = await self._meeting_reader.list_meetings(
            tenant_context=actor.tenant_context,
            include_cancelled=include_cancelled,
        )
        return tuple(
            MeetingState(
                google_event_id=m.google_event_id,
                meeting_id=m.id,
                title=m.title or "(untitled)",
                status=m.status.value,
                start_at=m.start_at,
                end_at=m.end_at,
                cancelled_at=m.cancelled_at,
            )
            for m in meetings
        )


class ActiveRuleRefreshAdapter:
    """Implements ActiveRuleRefreshPort over the calendar refresh adapter (D153).

    The evaluator is constructed once at startup but the calendar refresh
    adapter needs a resolved ``connection_id``, so this adapter resolves
    the tenant's google-calendar connection lazily on first refresh and
    caches the built delegate. A tenant with no calendar connection raises
    ``ActiveRuleRefreshError`` (the evaluator then evaluates over the
    last-synced state per D153).
    """

    def __init__(self, *, tenant_id: str) -> None:
        self._tenant_id = tenant_id
        self._delegate = None

    async def _resolve_connection_id(self) -> UUID | None:
        import sqlalchemy as sa

        from apps.cli._runtime import build_tenant_wiring
        from contexts.calendar.adapters.outbound.postgres._tables import (
            connections as calendar_connections_table,
        )

        session_factory = build_tenant_wiring(self._tenant_id).session_factory
        stmt = sa.select(calendar_connections_table.c.id).where(
            calendar_connections_table.c.tenant_id == self._tenant_id,
            calendar_connections_table.c.provider_config_key == "google-calendar",
        )
        async with session_factory() as session:
            row = (await session.execute(stmt)).first()
        return UUID(str(row[0])) if row is not None else None

    async def refresh(self, *, tenant_context: TenantContext) -> None:
        try:
            if self._delegate is None:
                connection_id = await self._resolve_connection_id()
                if connection_id is None:
                    raise ActiveRuleRefreshError(
                        f"no google-calendar connection for tenant {self._tenant_id}"
                    )
                from apps.cli._calendar import build_calendar_refresh_adapter

                self._delegate = build_calendar_refresh_adapter(
                    tenant_id=self._tenant_id, connection_id=connection_id
                )
            await self._delegate.refresh(tenant_context=tenant_context)
        except ActiveRuleRefreshError:
            raise
        except Exception as exc:  # CalendarRefreshError + any pipeline error
            raise ActiveRuleRefreshError(
                f"active-rule (calendar) refresh failed: {type(exc).__name__}: {exc}"
            ) from exc


class ThresholdCrossedEmitterAdapter:
    """Implements ThresholdCrossedEmitter via the D147 FireTrigger flow (D153)."""

    def __init__(
        self,
        *,
        fired_triggers_repository: FiredTriggersRepository,
        audit_port: AuditPort,
        broadcast_dispatch: BroadcastDispatch,
        jurisdiction: str,
        operator_timezone: str,
    ) -> None:
        self._fired = fired_triggers_repository
        self._audit = audit_port
        self._dispatch = broadcast_dispatch
        self._jurisdiction = jurisdiction
        self._operator_timezone = operator_timezone

    def _actor(self, *, tenant_id: UUID, user_id: str) -> ActorContext:
        role_list = frozenset({ROLE_OPERATOR})
        return ActorContext(
            tenant_context=TenantContext(
                tenant_id=str(tenant_id),
                jurisdiction=self._jurisdiction,
                cost_attribution_id=str(tenant_id),
            ),
            actor_id=user_id,
            role_list=role_list,
            authorisation_set=authorisations_for_roles(role_list),
        )

    async def emit(
        self, *, tenant_id: UUID, user_id: str, match: RuleMatch, triggered_at: str
    ) -> None:
        trigger_context = TriggerContext(
            trigger_type=BroadcastTriggerType.THRESHOLD_CROSSED,
            trigger_id=uuid4(),
            triggered_at=triggered_at,
            metadata=match.to_trigger_metadata(),
        )
        # The FireTrigger flow resolves the idempotency key from the
        # crossing identity (so a re-scan dedupes), inserts fired_triggers,
        # emits BROADCAST_INITIATED (carrying the crossing metadata), and
        # dispatches to the threshold-briefing implementer.
        await fire_trigger(
            fired_triggers_repository=self._fired,
            audit_port=self._audit,
            broadcast_dispatch=self._dispatch,
            actor=self._actor(tenant_id=tenant_id, user_id=user_id),
            trigger_context=trigger_context,
            operator_timezone=self._operator_timezone,
        )


class ThresholdNotifierAdapter:
    """Implements ThresholdNotifier via the messaging send_message use case (D146)."""

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
            message_intent=MessageIntent.BROADCAST_THRESHOLD_BRIEFING,
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
            message_intent=MessageIntent.BROADCAST_THRESHOLD_BRIEFING,
        )


def build_calendar_state_reader(*, tenant_id: str) -> CalendarStateReaderAdapter:  # pragma: no cover - composition-root wiring
    """Wire the calendar state reader for a tenant (D153)."""
    from apps.cli._runtime import build_tenant_wiring

    wiring = build_tenant_wiring(tenant_id)
    session_factory = wiring.session_factory

    async def _resolver(_tid):
        return session_factory

    return CalendarStateReaderAdapter(
        meeting_reader=PostgresMeetingStore(
            per_tenant_sessionmaker_resolver=_resolver,
            bound_tenant_id=TenantId(tenant_id),
        )
    )


__all__ = [
    "ActiveRuleRefreshAdapter",
    "CalendarStateReaderAdapter",
    "ThresholdCrossedEmitterAdapter",
    "ThresholdNotifierAdapter",
    "build_calendar_state_reader",
]
