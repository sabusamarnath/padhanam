"""record_intake use case (D127, D128).

Mints an IntakeRecord, persists it through the repository, and emits
an ``intake.record.create`` audit event. The standalone intake path
— the operator-records-without-acting surface, and the building
block the orchestration use cases compose.

S44b (D126/D127): accepts an ActorContext, applies the
``requires_authorisation`` decorator at the boundary, extracts
``actor.tenant_context`` for the adapter call, and derives an
``ActorReference`` from ``actor.actor_id`` for the persisted
authoring identity.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from contexts.audit.domain.ports import AuditPort

from contexts.intake.application.audit_events import draft_intake_record
from contexts.intake.domain import IntakePayload, IntakeRecord, IntakeSource
from contexts.intake.ports.intake_repository import IntakeRepository
from shared_kernel import ActorContext, ActorReference
from shared_kernel.authorisation import (
    INTAKE_RECORD_CREATE,
    requires_authorisation,
)


@requires_authorisation(INTAKE_RECORD_CREATE)
async def record_intake(
    *,
    repository: IntakeRepository,
    audit_port: AuditPort,
    actor: ActorContext,
    intake_source: IntakeSource,
    payload: IntakePayload,
) -> IntakeRecord:
    """Create and persist an IntakeRecord; emit the audit event."""
    tenant_context = actor.tenant_context
    authored_by = ActorReference(user_id=actor.actor_id)
    intake = IntakeRecord(
        id=uuid4(),
        tenant_id=UUID(tenant_context.tenant_id),
        jurisdiction=tenant_context.jurisdiction,
        intake_source=intake_source,
        payload=payload,
        authored_by=authored_by,
        created_at=datetime.now(timezone.utc),
    )
    await repository.save(tenant_context=tenant_context, intake=intake)
    await audit_port.emit(
        draft_intake_record(
            tenant_context=tenant_context, intake=intake, actor=authored_by
        )
    )
    return intake


__all__ = ["record_intake"]
