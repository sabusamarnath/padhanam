"""Draft-audit-event helper for the messaging context (D129).

Per D110 commitment 7 every messaging write emits an audit event;
the audit context's existing chain integrity transitively
guarantees tamper-evidence on the message records — there is no
parallel hash chain on the `messages` table.

The Postgres audit adapter recomputes ``previous_event_hash`` and
``this_event_hash`` inside its locking transaction per D37; the
placeholders here are draft values the adapter overwrites.

Resource type ``message``; the action verb is derived from the
Message direction — ``messaging.message.send`` for an outbound
Message, ``messaging.message.receive`` for an inbound one.
"""

from __future__ import annotations

from datetime import datetime, timezone

from contexts.audit.domain.events import (
    GENESIS_HASH,
    AuditEvent,
    compute_event_hash,
)

from contexts.messaging.domain import Message, MessageDirection
from shared_kernel import ActorReference, TenantContext

RESOURCE_TYPE_MESSAGE: str = "message"
ACTION_MESSAGE_SEND: str = "messaging.message.send"
ACTION_MESSAGE_RECEIVE: str = "messaging.message.receive"


def draft_message_event(
    *,
    tenant_context: TenantContext,
    message: Message,
    actor: ActorReference,
    correlation_id: str = "",
) -> AuditEvent:
    """Draft the audit event for a messaging write.

    The action verb follows the Message direction so a single helper
    serves both the outbound send and the inbound receive paths.
    """
    action_verb = (
        ACTION_MESSAGE_SEND
        if message.direction is MessageDirection.OUTBOUND
        else ACTION_MESSAGE_RECEIVE
    )
    timestamp = datetime.now(timezone.utc).isoformat()
    after_state = {
        "direction": message.direction.value,
        "channel": message.channel.value,
        "status": message.status.value,
        "external_id": message.external_id,
        "intake_id": (
            None if message.intake_id is None else str(message.intake_id)
        ),
        "created_at": message.created_at.isoformat(),
    }
    draft_hash = compute_event_hash(
        actor=actor.user_id,
        tenant_id=tenant_context.tenant_id,
        jurisdiction=tenant_context.jurisdiction,
        timestamp=timestamp,
        action_verb=action_verb,
        resource_type=RESOURCE_TYPE_MESSAGE,
        resource_id=str(message.id),
        before_state={},
        after_state=after_state,
        correlation_id=correlation_id,
        previous_event_hash=GENESIS_HASH,
    )
    return AuditEvent(
        actor=actor.user_id,
        tenant_id=tenant_context.tenant_id,
        jurisdiction=tenant_context.jurisdiction,
        timestamp=timestamp,
        action_verb=action_verb,
        resource_type=RESOURCE_TYPE_MESSAGE,
        resource_id=str(message.id),
        before_state={},
        after_state=after_state,
        correlation_id=correlation_id,
        previous_event_hash=GENESIS_HASH,
        this_event_hash=draft_hash,
    )


__all__ = [
    "ACTION_MESSAGE_RECEIVE",
    "ACTION_MESSAGE_SEND",
    "RESOURCE_TYPE_MESSAGE",
    "draft_message_event",
]
