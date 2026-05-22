"""record_inbound_message use case (D128, D129).

The plain inbound-persistence use case: it mints an INBOUND Message
with status RECEIVED, persists it, and emits the audit event. It
does *not* record an IntakeRecord — that is the intake-context
orchestration's job. The ``record_intake_and_record_inbound_message``
orchestration at ``contexts/intake/application/`` records the
IntakeRecord first, then drives this use case through the
``MessageWriter`` consumer port with the resulting ``intake_id``
per D127 alternative (d).

This use case is invoked through that consumer port; it carries its
own ``messaging.message.receive`` decorator so the authorisation
check fail-fasts whether reached via the orchestration or directly.
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
    MessageStatus,
)
from contexts.messaging.ports.message_repository import MessageRepository
from shared_kernel import ActorContext, ActorReference
from shared_kernel.authorisation import (
    MESSAGING_MESSAGE_RECEIVE,
    requires_authorisation,
)


@requires_authorisation(MESSAGING_MESSAGE_RECEIVE)
async def record_inbound_message(
    *,
    repository: MessageRepository,
    audit_port: AuditPort,
    actor: ActorContext,
    from_address: str,
    to_address: str,
    body: str,
    intake_id: UUID,
    external_id: str | None = None,
    channel: MessageChannel = MessageChannel.WHATSAPP,
) -> Message:
    """Persist an inbound Message carrying its IntakeRecord's id."""
    tenant_context = actor.tenant_context
    authored_by = ActorReference(user_id=actor.actor_id)
    message = Message(
        id=uuid4(),
        tenant_id=UUID(tenant_context.tenant_id),
        jurisdiction=tenant_context.jurisdiction,
        direction=MessageDirection.INBOUND,
        channel=channel,
        body=body,
        from_address=from_address,
        to_address=to_address,
        status=MessageStatus.RECEIVED,
        actor_id=actor.actor_id,
        created_at=datetime.now(timezone.utc),
        external_id=external_id,
        intake_id=intake_id,
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


__all__ = ["record_inbound_message"]
