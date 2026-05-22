"""Draft-audit-event helper for the intake context (D127, D128).

Per D110 commitment 7 every intake write emits an audit event; the
audit context's existing chain integrity transitively guarantees
tamper-evidence on the intake records — there is no parallel hash
chain on the `intakes` table.

The Postgres audit adapter recomputes ``previous_event_hash`` and
``this_event_hash`` inside its locking transaction per D37; the
placeholders here are draft values the adapter overwrites.

Resource type ``intake`` for the IntakeRecord aggregate; action
verb ``intake.record.create``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from contexts.audit.domain.events import (
    GENESIS_HASH,
    AuditEvent,
    compute_event_hash,
)

from contexts.intake.domain import IntakeRecord
from shared_kernel import ActorReference, TenantContext

RESOURCE_TYPE_INTAKE: str = "intake"
ACTION_INTAKE_RECORD_CREATE: str = "intake.record.create"


def draft_intake_record(
    *,
    tenant_context: TenantContext,
    intake: IntakeRecord,
    actor: ActorReference,
    correlation_id: str = "",
) -> AuditEvent:
    """Draft the ``intake.record.create`` audit event for an IntakeRecord."""
    timestamp = datetime.now(timezone.utc).isoformat()
    after_state = {
        "intake_source": intake.intake_source.value,
        "intent_hint": intake.payload.intent_hint,
        "created_at": intake.created_at.isoformat(),
    }
    draft_hash = compute_event_hash(
        actor=actor.user_id,
        tenant_id=tenant_context.tenant_id,
        jurisdiction=tenant_context.jurisdiction,
        timestamp=timestamp,
        action_verb=ACTION_INTAKE_RECORD_CREATE,
        resource_type=RESOURCE_TYPE_INTAKE,
        resource_id=str(intake.id),
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
        action_verb=ACTION_INTAKE_RECORD_CREATE,
        resource_type=RESOURCE_TYPE_INTAKE,
        resource_id=str(intake.id),
        before_state={},
        after_state=after_state,
        correlation_id=correlation_id,
        previous_event_hash=GENESIS_HASH,
        this_event_hash=draft_hash,
    )


__all__ = [
    "ACTION_INTAKE_RECORD_CREATE",
    "RESOURCE_TYPE_INTAKE",
    "draft_intake_record",
]
