"""create_pending_clarification use case (D134, S47).

The cell calls this use case after a medium-confidence intent
classification: it expires any prior PENDING for the same
``(tenant_id, user_id)`` per the D134 invariant, then persists the
new PENDING and emits its lifecycle audit event.

Two writes flow through one transaction at the repository level when
a prior PENDING exists; the implementation guards order so the
expiry lands before the create (mirrors the migration's partial
unique-index expectation).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from contexts.audit.domain.ports import AuditPort

from contexts.messaging.application.audit_events import (
    draft_pending_clarification_created_event,
    draft_pending_clarification_expired_event,
)
from contexts.messaging.domain.pending_clarification import (
    PendingClarification,
    PendingClarificationStatus,
)
from contexts.messaging.ports.pending_clarification_repository import (
    PendingClarificationRepository,
)
from shared_kernel import ActorContext, ActorReference
from shared_kernel.authorisation import (
    MESSAGING_PENDING_CLARIFICATION_CREATE,
    requires_authorisation,
)

# D119: WhatsApp customer-service window is 24 hours; align the
# default expiry so a PendingClarification cannot outlive the channel
# affordances that gave rise to it.
_DEFAULT_TTL = timedelta(hours=24)


@requires_authorisation(MESSAGING_PENDING_CLARIFICATION_CREATE)
async def create_pending_clarification(
    *,
    repository: PendingClarificationRepository,
    audit_port: AuditPort,
    actor: ActorContext,
    user_id: str,
    originating_channel: str,
    originating_user_address: str,
    originating_intake_id: UUID,
    proposed_intent: dict[str, Any],
    proposed_action_summary: str,
    target_cell: str,
    ttl: timedelta = _DEFAULT_TTL,
) -> PendingClarification:
    """Expire any prior PENDING for (tenant, user); create a new PENDING.

    ``target_cell`` (D140, S52) identifies which ConversationFlow
    implementer owns the new pending. Existing callers pass
    ``"manual_entry"`` (S47/S50) or ``"audit_conversation"`` (S51);
    S52 mirror-conversation passes ``"mirror_conversation"``; the
    meta-classification PendingClarification at D140 dispatch flow
    Step 5 passes ``"dispatch_clarification"``.
    """
    tenant_context = actor.tenant_context
    authored_by = ActorReference(user_id=actor.actor_id)
    now = datetime.now(timezone.utc)

    prior = await repository.get_active_for_user(
        tenant_context=tenant_context,
        user_id=user_id,
    )
    if prior is not None:
        expired = prior.expire(at=now)
        await repository.update_status(
            tenant_context=tenant_context, pending=expired
        )
        await audit_port.emit(
            draft_pending_clarification_expired_event(
                tenant_context=tenant_context,
                pending=expired,
                actor=authored_by,
            )
        )

    pending = PendingClarification(
        id=uuid4(),
        tenant_id=UUID(tenant_context.tenant_id),
        jurisdiction=tenant_context.jurisdiction,
        user_id=user_id,
        originating_channel=originating_channel,
        originating_user_address=originating_user_address,
        originating_intake_id=originating_intake_id,
        proposed_intent=proposed_intent,
        proposed_action_summary=proposed_action_summary,
        status=PendingClarificationStatus.PENDING,
        target_cell=target_cell,
        created_at=now,
        expires_at=now + ttl,
    )
    await repository.save(tenant_context=tenant_context, pending=pending)
    await audit_port.emit(
        draft_pending_clarification_created_event(
            tenant_context=tenant_context,
            pending=pending,
            actor=authored_by,
        )
    )
    return pending


__all__ = ["create_pending_clarification"]
