"""send_message use case (D129).

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
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from contexts.audit.domain.ports import AuditPort

from contexts.messaging.application.audit_events import draft_message_event
from contexts.messaging.domain import (
    Message,
    MessageChannel,
    MessageDirection,
)
from contexts.messaging.ports.message_delivery_port import MessageDeliveryPort
from contexts.messaging.ports.message_repository import MessageRepository
from shared_kernel import ActorContext, ActorReference
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
    actor: ActorContext,
    from_address: str,
    to_address: str,
    body: str,
    channel: MessageChannel = MessageChannel.WHATSAPP,
) -> Message:
    """Deliver an outbound message, persist it, and emit the audit event."""
    tenant_context = actor.tenant_context
    authored_by = ActorReference(user_id=actor.actor_id)
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
