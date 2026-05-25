"""resolve_pending_clarification use case (D134, S47).

The cell calls this use case when an operator reply resolves an
active PendingClarification — either as a confirmation ("yes" /
"confirm" / "that's right") or a cancellation ("no" / "actually...").
The audit event's ``resolution`` tag distinguishes the two paths so
the audit chain carries operator intent verbatim.
"""

from __future__ import annotations

from datetime import datetime, timezone

from contexts.audit.domain.ports import AuditPort

from contexts.messaging.application.audit_events import (
    draft_pending_clarification_resolved_event,
)
from contexts.messaging.domain.pending_clarification import (
    PendingClarification,
)
from contexts.messaging.ports.pending_clarification_repository import (
    PendingClarificationRepository,
)
from shared_kernel import ActorContext, ActorReference
from shared_kernel.authorisation import (
    MESSAGING_PENDING_CLARIFICATION_RESOLVE,
    requires_authorisation,
)


@requires_authorisation(MESSAGING_PENDING_CLARIFICATION_RESOLVE)
async def resolve_pending_clarification(
    *,
    repository: PendingClarificationRepository,
    audit_port: AuditPort,
    actor: ActorContext,
    pending: PendingClarification,
    resolution: str,
) -> PendingClarification:
    """Transition a PENDING clarification to RESOLVED."""
    tenant_context = actor.tenant_context
    authored_by = ActorReference(user_id=actor.actor_id)
    now = datetime.now(timezone.utc)

    resolved = pending.resolve(at=now)
    await repository.update_status(
        tenant_context=tenant_context, pending=resolved
    )
    await audit_port.emit(
        draft_pending_clarification_resolved_event(
            tenant_context=tenant_context,
            pending=resolved,
            actor=authored_by,
            resolution=resolution,
        )
    )
    return resolved


__all__ = ["resolve_pending_clarification"]
