"""send_message use case (D129, D144).

The outbound messaging use case behind POST ``/api/v1/messaging/send``.
It delivers the message through the ``MessageDeliveryPort`` first,
then persists the Message carrying the vendor's accepted status and
external id, then emits the audit event.

Delivery precedes persistence because the Message aggregate is
immutable — a QUEUED record cannot later be updated to SENT, so the
record is written once, in its delivered state. A delivery
exception propagates and nothing persists; a delivered-with-FAILED
result persists honestly as a FAILED Message.

S45 (D126/D129): accepts an ActorContext, applies the
``requires_authorisation`` decorator at the boundary, and stamps
``actor.actor_id`` as the Message's acting actor.

S53 (D144): consults the ChannelResolver port before delivery. At
Phase 2-A the static-config resolver adapter returns the operator-
default channel regardless of input — identity routing for reactive
outbound (the inbound arrived from the operator's WhatsApp; the
resolved channel resolves to WhatsApp; the channel adapter sends via
WhatsApp). The consultation is the structural seam at which multi-
channel activation later swaps the adapter without touching this use
case. The ``channel`` kwarg stays as the caller-supplied destination
hint per the pre-S53 shape; future multi-channel activation makes
the resolver authoritative and the ``channel`` kwarg becomes legacy.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from contexts.audit.domain.ports import AuditPort

from contexts.messaging.application.audit_events import draft_message_event
from contexts.messaging.application.ports.channel_resolver import (
    ChannelResolver,
)
from contexts.messaging.domain import (
    Message,
    MessageChannel,
    MessageDirection,
)
from contexts.messaging.ports.message_delivery_port import MessageDeliveryPort
from contexts.messaging.ports.message_repository import MessageRepository
from shared_kernel import ActorContext, ActorReference, MessageIntent
from shared_kernel.authorisation import (
    MESSAGING_MESSAGE_SEND,
    requires_authorisation,
)


@requires_authorisation(MESSAGING_MESSAGE_SEND)
async def send_message(
    *,
    repository: MessageRepository,
    delivery_port: MessageDeliveryPort,
    audit_port: AuditPort,
    channel_resolver: ChannelResolver,
    actor: ActorContext,
    from_address: str,
    to_address: str,
    body: str,
    channel: MessageChannel = MessageChannel.WHATSAPP,
    message_intent: MessageIntent = MessageIntent.REACTIVE_RESPONSE,
    cell_payload: dict[str, Any] | None = None,
) -> Message:
    """Deliver an outbound message, persist it, and emit the audit event.

    ``cell_payload`` (D141, S52) is the per-implementer JSONB payload
    a ConversationFlow implementer attaches to the outbound message
    for cross-turn state extraction. Defaults to ``None`` so existing
    call sites (manual entry cell, audit-conversation cell, plain
    HTTP send) preserve their behaviour. Mirror-conversation at S52
    is the first user.

    ``message_intent`` (D144, S53) discriminates the resolver input;
    defaults to ``REACTIVE_RESPONSE`` because every existing call
    site (manual entry, audit-conversation, mirror-conversation,
    plain HTTP send, dispatch_inbound) is a reactive-response send.
    BroadcastFlow implementers at S54+ pass
    ``BROADCAST_DAILY_BRIEFING`` or ``BROADCAST_THRESHOLD_BRIEFING``.
    """
    tenant_context = actor.tenant_context
    authored_by = ActorReference(user_id=actor.actor_id)
    # D144 (S53): consult ChannelResolver before delivery. At Phase 2-A
    # the static-config adapter returns the operator-default channel
    # (WhatsApp) regardless of input. The resolved destination is the
    # observable forward-compat surface — at multi-channel activation
    # the resolver becomes authoritative and the ``channel`` kwarg
    # converges to legacy. At Phase 2-A the resolution is identity:
    # the resolved channel matches the kwarg by construction.
    await channel_resolver.resolve_channel(
        tenant_id=UUID(tenant_context.tenant_id),
        user_id=actor.actor_id,
        message_intent=message_intent,
    )
    result = await delivery_port.send(
        channel=channel,
        from_address=from_address,
        to_address=to_address,
        body=body,
    )
    message = Message(
        id=uuid4(),
        tenant_id=UUID(tenant_context.tenant_id),
        jurisdiction=tenant_context.jurisdiction,
        direction=MessageDirection.OUTBOUND,
        channel=channel,
        body=body,
        from_address=from_address,
        to_address=to_address,
        status=result.status,
        actor_id=actor.actor_id,
        created_at=datetime.now(timezone.utc),
        external_id=result.external_id,
        intake_id=None,
        cell_payload=cell_payload,
    )
    await repository.save(tenant_context=tenant_context, message=message)
    await audit_port.emit(
        draft_message_event(
            tenant_context=tenant_context,
            message=message,
            actor=authored_by,
        )
    )
    return message


__all__ = ["send_message"]
