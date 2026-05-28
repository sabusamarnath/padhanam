"""Draft-audit-event helper for the messaging context (D129, D134).

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

D134 (S47) adds the PendingClarification lifecycle audit events —
``messaging.pending_clarification.create / resolve / expire`` —
sharing the same draft-then-recompute pattern.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from contexts.audit.domain.events import (
    GENESIS_HASH,
    AuditEvent,
    compute_event_hash,
)

from contexts.messaging.domain import Message, MessageDirection
from contexts.messaging.domain.pending_clarification import (
    PendingClarification,
)
from shared_kernel import ActorReference, TenantContext

RESOURCE_TYPE_MESSAGE: str = "message"
ACTION_MESSAGE_SEND: str = "messaging.message.send"
ACTION_MESSAGE_RECEIVE: str = "messaging.message.receive"

RESOURCE_TYPE_PENDING_CLARIFICATION: str = "pending_clarification"
ACTION_PENDING_CLARIFICATION_CREATE: str = (
    "messaging.pending_clarification.create"
)
ACTION_PENDING_CLARIFICATION_RESOLVE: str = (
    "messaging.pending_clarification.resolve"
)
ACTION_PENDING_CLARIFICATION_EXPIRE: str = (
    "messaging.pending_clarification.expire"
)

# D147 (S54): BROADCAST_INITIATED audit event for platform-initiated
# broadcasts. Per S54 pre-write reconciliation Finding 1 there is no
# discrete audit "event class set" at contexts/audit/domain/; audit
# events use action_verb + resource_type strings and per-context
# audit_events.py modules define the constants. The broadcast event
# fires at the HTTP trigger endpoint after a fresh idempotency-check
# insert and before BroadcastDispatch invocation. BroadcastFlow
# implementers cite this event's id via cited_audit_events per D131.
RESOURCE_TYPE_BROADCAST: str = "broadcast"
ACTION_BROADCAST_INITIATED: str = "messaging.broadcast.initiated"


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


def _draft_pending_clarification_event(
    *,
    tenant_context: TenantContext,
    pending: PendingClarification,
    actor: ActorReference,
    action_verb: str,
    before_state: dict[str, object],
    after_state: dict[str, object],
    correlation_id: str = "",
) -> AuditEvent:
    """Shared draft helper for the three PendingClarification lifecycle events."""
    timestamp = datetime.now(timezone.utc).isoformat()
    draft_hash = compute_event_hash(
        actor=actor.user_id,
        tenant_id=tenant_context.tenant_id,
        jurisdiction=tenant_context.jurisdiction,
        timestamp=timestamp,
        action_verb=action_verb,
        resource_type=RESOURCE_TYPE_PENDING_CLARIFICATION,
        resource_id=str(pending.id),
        before_state=before_state,
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
        resource_type=RESOURCE_TYPE_PENDING_CLARIFICATION,
        resource_id=str(pending.id),
        before_state=before_state,
        after_state=after_state,
        correlation_id=correlation_id,
        previous_event_hash=GENESIS_HASH,
        this_event_hash=draft_hash,
    )


def draft_pending_clarification_created_event(
    *,
    tenant_context: TenantContext,
    pending: PendingClarification,
    actor: ActorReference,
    correlation_id: str = "",
) -> AuditEvent:
    """Audit event for PendingClarification create (status PENDING)."""
    after_state = {
        "status": pending.status.value,
        "user_id": pending.user_id,
        "originating_channel": pending.originating_channel,
        "originating_intake_id": str(pending.originating_intake_id),
        "proposed_action_summary": pending.proposed_action_summary,
        "expires_at": pending.expires_at.isoformat(),
    }
    return _draft_pending_clarification_event(
        tenant_context=tenant_context,
        pending=pending,
        actor=actor,
        action_verb=ACTION_PENDING_CLARIFICATION_CREATE,
        before_state={},
        after_state=after_state,
        correlation_id=correlation_id,
    )


def draft_pending_clarification_resolved_event(
    *,
    tenant_context: TenantContext,
    pending: PendingClarification,
    actor: ActorReference,
    resolution: str,
    correlation_id: str = "",
) -> AuditEvent:
    """Audit event for PendingClarification resolve (PENDING → RESOLVED).

    ``resolution`` is a short tag (e.g. ``"confirmed"``, ``"cancelled"``)
    so the audit record distinguishes the two operator paths.
    """
    after_state = {
        "status": pending.status.value,
        "user_id": pending.user_id,
        "resolved_at": (
            pending.resolved_at.isoformat()
            if pending.resolved_at is not None
            else None
        ),
        "resolution": resolution,
    }
    return _draft_pending_clarification_event(
        tenant_context=tenant_context,
        pending=pending,
        actor=actor,
        action_verb=ACTION_PENDING_CLARIFICATION_RESOLVE,
        before_state={"status": "PENDING"},
        after_state=after_state,
        correlation_id=correlation_id,
    )


def draft_pending_clarification_expired_event(
    *,
    tenant_context: TenantContext,
    pending: PendingClarification,
    actor: ActorReference,
    correlation_id: str = "",
) -> AuditEvent:
    """Audit event for PendingClarification expire (PENDING → EXPIRED)."""
    after_state = {
        "status": pending.status.value,
        "user_id": pending.user_id,
        "resolved_at": (
            pending.resolved_at.isoformat()
            if pending.resolved_at is not None
            else None
        ),
    }
    return _draft_pending_clarification_event(
        tenant_context=tenant_context,
        pending=pending,
        actor=actor,
        action_verb=ACTION_PENDING_CLARIFICATION_EXPIRE,
        before_state={"status": "PENDING"},
        after_state=after_state,
        correlation_id=correlation_id,
    )


def draft_broadcast_initiated_event(
    *,
    tenant_context: TenantContext,
    actor: ActorReference,
    trigger_id: UUID,
    trigger_type: str,
    user_id: str,
    triggered_at: str,
    correlation_id: str = "",
) -> AuditEvent:
    """Draft the BROADCAST_INITIATED audit event for a fresh trigger fire (D147).

    Resource type ``broadcast``; action verb
    ``messaging.broadcast.initiated``. The ``resource_id`` is the
    ``trigger_id`` so a BroadcastFlow implementer's response can cite
    this event via ``cited_audit_events`` for chain traversability
    per D131. The after_state records the trigger's identifying
    metadata; before_state is empty (the broadcast did not exist
    before this fire). The adapter recomputes the chain hashes inside
    its locking transaction per D37; the placeholder here is a draft
    value the adapter overwrites.
    """
    after_state = {
        "trigger_id": str(trigger_id),
        "trigger_type": trigger_type,
        "user_id": user_id,
        "triggered_at": triggered_at,
    }
    draft_hash = compute_event_hash(
        actor=actor.user_id,
        tenant_id=tenant_context.tenant_id,
        jurisdiction=tenant_context.jurisdiction,
        timestamp=triggered_at,
        action_verb=ACTION_BROADCAST_INITIATED,
        resource_type=RESOURCE_TYPE_BROADCAST,
        resource_id=str(trigger_id),
        before_state={},
        after_state=after_state,
        correlation_id=correlation_id,
        previous_event_hash=GENESIS_HASH,
    )
    return AuditEvent(
        actor=actor.user_id,
        tenant_id=tenant_context.tenant_id,
        jurisdiction=tenant_context.jurisdiction,
        timestamp=triggered_at,
        action_verb=ACTION_BROADCAST_INITIATED,
        resource_type=RESOURCE_TYPE_BROADCAST,
        resource_id=str(trigger_id),
        before_state={},
        after_state=after_state,
        correlation_id=correlation_id,
        previous_event_hash=GENESIS_HASH,
        this_event_hash=draft_hash,
    )


__all__ = [
    "ACTION_BROADCAST_INITIATED",
    "ACTION_MESSAGE_RECEIVE",
    "ACTION_MESSAGE_SEND",
    "ACTION_PENDING_CLARIFICATION_CREATE",
    "ACTION_PENDING_CLARIFICATION_EXPIRE",
    "ACTION_PENDING_CLARIFICATION_RESOLVE",
    "RESOURCE_TYPE_BROADCAST",
    "RESOURCE_TYPE_MESSAGE",
    "RESOURCE_TYPE_PENDING_CLARIFICATION",
    "draft_broadcast_initiated_event",
    "draft_message_event",
    "draft_pending_clarification_created_event",
    "draft_pending_clarification_expired_event",
    "draft_pending_clarification_resolved_event",
]
