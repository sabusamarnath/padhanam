"""FireTrigger use case — HTTP trigger endpoint orchestration (D145, D147, S54).

Implements the seven-step endpoint flow per D147. The HTTP route at
``apps/api/routers/triggers.py`` delegates to this use case after the
internal-secret middleware authenticates the request and the router
parses the payload into a TriggerContext.

The flow:

1. Resolve the idempotency_key per trigger_type via the resolver at
   ``contexts/messaging/domain/idempotency.py``.
2. INSERT into fired_triggers via FiredTriggersRepository.insert_or_skip
   (race-safe ON CONFLICT DO NOTHING per D147).
3. If the insert returned False (conflict / duplicate): return
   ``FireTriggerResult`` with status ALREADY_FIRED and log structured
   "already fired"; exit without audit-chain or dispatch side effects.
4. If the insert returned True (fresh): emit the BROADCAST_INITIATED
   audit event.
5. Invoke BroadcastDispatch.dispatch with the TriggerContext.
6. Return ``FireTriggerResult`` with status ACCEPTED.

Best-effort delivery between INSERT and dispatch per D147: the
fired_triggers row plus the BROADCAST_INITIATED event together record
the attempt; a dispatch exception propagates to the caller, which
surfaces it but does not roll back the idempotency row (two-phase
commit defers to the dogfooding-evidence activation trigger).

Application layer is framework-free here — stdlib plus shared_kernel
plus the messaging ports.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from contexts.audit.domain.ports import AuditPort

from contexts.messaging.application.audit_events import (
    draft_broadcast_initiated_event,
)
from contexts.messaging.application.ports.broadcast_dispatch import (
    BroadcastDispatch,
)
from contexts.messaging.domain.idempotency import resolve_idempotency_key
from contexts.messaging.ports.fired_triggers_repository import (
    FiredTriggersRepository,
)
from shared_kernel import ActorContext, ActorReference
from shared_kernel.authorisation import (
    MESSAGING_MESSAGE_SEND,
    requires_authorisation,
)
from shared_kernel.broadcast_flow import TriggerContext

_logger = logging.getLogger("padhanam.messaging.fire_trigger")


class FireTriggerStatus(StrEnum):
    """The outcome of a FireTrigger invocation."""

    ACCEPTED = "accepted"
    ALREADY_FIRED = "already_fired"


@dataclass(frozen=True)
class FireTriggerResult:
    """The structured outcome the HTTP route translates into a response."""

    status: FireTriggerStatus
    trigger_id: str


@requires_authorisation(MESSAGING_MESSAGE_SEND)
async def fire_trigger(
    *,
    fired_triggers_repository: FiredTriggersRepository,
    audit_port: AuditPort,
    broadcast_dispatch: BroadcastDispatch,
    actor: ActorContext,
    trigger_context: TriggerContext,
    operator_timezone: str,
) -> FireTriggerResult:
    """Execute the D147 seven-step endpoint flow; return the outcome.

    ``actor`` is the synthesised operator ActorContext for the
    configured webhook/broadcast tenant (the internal trigger
    endpoint carries no per-user Principal; the deployment's
    scheduler fires on the operator's behalf). The
    ``MESSAGING_MESSAGE_SEND`` authorisation gates the broadcast send
    (the broadcast culminates in an outbound message).
    """
    tenant_context = actor.tenant_context
    user_id = actor.actor_id

    idempotency_key = resolve_idempotency_key(
        trigger_type=trigger_context.trigger_type,
        metadata=trigger_context.metadata,
        operator_timezone=operator_timezone,
    )

    fresh = await fired_triggers_repository.insert_or_skip(
        tenant_context=tenant_context,
        user_id=user_id,
        trigger_type=trigger_context.trigger_type.value,
        idempotency_key=idempotency_key,
    )

    if not fresh:
        _logger.info(
            "broadcast trigger already fired; skipping dispatch",
            extra={
                "context": {
                    "trigger_id": str(trigger_context.trigger_id),
                    "trigger_type": trigger_context.trigger_type.value,
                    "tenant_id": str(tenant_context.tenant_id),
                    "user_id": user_id,
                    "idempotency_key": idempotency_key,
                }
            },
        )
        return FireTriggerResult(
            status=FireTriggerStatus.ALREADY_FIRED,
            trigger_id=str(trigger_context.trigger_id),
        )

    await audit_port.emit(
        draft_broadcast_initiated_event(
            tenant_context=tenant_context,
            actor=ActorReference(user_id=user_id),
            trigger_id=trigger_context.trigger_id,
            trigger_type=trigger_context.trigger_type.value,
            user_id=user_id,
            triggered_at=trigger_context.triggered_at,
            metadata=trigger_context.metadata,
        )
    )

    await broadcast_dispatch.dispatch(
        tenant_id=UUID(str(tenant_context.tenant_id)),
        user_id=user_id,
        trigger_context=trigger_context,
        context={
            "idempotency_key": idempotency_key,
        },
    )

    return FireTriggerResult(
        status=FireTriggerStatus.ACCEPTED,
        trigger_id=str(trigger_context.trigger_id),
    )


__all__ = [
    "FireTriggerResult",
    "FireTriggerStatus",
    "fire_trigger",
]
