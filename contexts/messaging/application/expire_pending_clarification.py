"""expire_pending_clarification use case (D134, S47).

Transitions a PENDING clarification to EXPIRED. Phase 2-A: invoked
opportunistically by the cell at turn-open when it discovers a
PENDING whose ``expires_at`` has elapsed. A scheduled-sweep job is a
Phase 2-B+ activation (the deferred-decisions entry under
``scheduled-runs primitive``); Phase 2-A's degenerate single-user
single-channel reality keeps the opportunistic-expiry path
sufficient.
"""

from __future__ import annotations

from datetime import datetime

from contexts.audit.domain.ports import AuditPort

from contexts.messaging.application.audit_events import (
    draft_pending_clarification_expired_event,
)
from contexts.messaging.domain.pending_clarification import (
    PendingClarification,
)
from contexts.messaging.ports.pending_clarification_repository import (
    PendingClarificationRepository,
)
from shared_kernel import ActorContext, ActorReference
from shared_kernel.authorisation import (
    MESSAGING_PENDING_CLARIFICATION_EXPIRE,
    requires_authorisation,
)


@requires_authorisation(MESSAGING_PENDING_CLARIFICATION_EXPIRE)
async def expire_pending_clarification(
    *,
    repository: PendingClarificationRepository,
    audit_port: AuditPort,
    actor: ActorContext,
    pending: PendingClarification,
    now: datetime,
) -> PendingClarification:
    """Transition a PENDING clarification to EXPIRED.

    ``now`` is the expiry instant, supplied by the caller through the clock
    seam (S75): a cell passes its per-turn ``self._clock()`` so the EXPIRED
    stamp shares the turn's single notion of "now" and stays deterministic in
    tests — the read is required, not minted here, so it cannot become
    wall-clock-by-luck.
    """
    tenant_context = actor.tenant_context
    authored_by = ActorReference(user_id=actor.actor_id)

    expired = pending.expire(at=now)
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
    return expired


__all__ = ["expire_pending_clarification"]
