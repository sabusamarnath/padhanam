"""Draft audit events for CDD-evidence corrections (D203, S103c).

A relink or unlink is a state change on tenant-authored canonical data, so it is
recorded in the audit trail (the platform's audit-trail-as-source-of-truth
commitment) — and the same hash-chained record is the **learning signal** a later
session reads back (the labelled prior→new binding pair). Mirrors the optimization
runner's audit-event drafting (the Postgres adapter is the chain authority and
recomputes ``previous_event_hash`` / ``this_event_hash`` inside its locking
transaction per D37; the placeholders here are draft values it overwrites).

Resource type ``cdd_element_evidence``; action verbs ``cdd.relink`` / ``cdd.unlink``
(the faceted query the consume session filters on). ``before_state`` is the prior
binding, ``after_state`` the new binding (empty for an unlink).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from contexts.audit.domain.events import (
    GENESIS_HASH,
    AuditEvent,
    compute_event_hash,
)
from shared_kernel import TenantContext

RESOURCE_TYPE_CDD_EVIDENCE: str = "cdd_element_evidence"
ACTION_CDD_RELINK: str = "cdd.relink"
ACTION_CDD_UNLINK: str = "cdd.unlink"


def _draft(
    *,
    tenant_context: TenantContext,
    actor: str,
    action_verb: str,
    resource_id: str,
    before_state: dict,
    after_state: dict,
    correlation_id: str = "",
) -> AuditEvent:
    timestamp = datetime.now(timezone.utc).isoformat()
    draft_hash = compute_event_hash(
        actor=actor,
        tenant_id=tenant_context.tenant_id,
        jurisdiction=tenant_context.jurisdiction,
        timestamp=timestamp,
        action_verb=action_verb,
        resource_type=RESOURCE_TYPE_CDD_EVIDENCE,
        resource_id=resource_id,
        before_state=before_state,
        after_state=after_state,
        correlation_id=correlation_id,
        previous_event_hash=GENESIS_HASH,
    )
    return AuditEvent(
        actor=actor,
        tenant_id=tenant_context.tenant_id,
        jurisdiction=tenant_context.jurisdiction,
        timestamp=timestamp,
        action_verb=action_verb,
        resource_type=RESOURCE_TYPE_CDD_EVIDENCE,
        resource_id=resource_id,
        before_state=before_state,
        after_state=after_state,
        correlation_id=correlation_id,
        previous_event_hash=GENESIS_HASH,
        this_event_hash=draft_hash,
    )


def relink_correction_event(
    *,
    tenant_context: TenantContext,
    actor: str,
    unit_id: UUID,
    from_kind: str,
    from_element_id: UUID,
    to_kind: str,
    to_element_id: UUID,
) -> AuditEvent:
    """The append-only record of a relink (the prior→new labelled pair)."""
    return _draft(
        tenant_context=tenant_context,
        actor=actor,
        action_verb=ACTION_CDD_RELINK,
        resource_id=str(unit_id),
        before_state={
            "unit_id": str(unit_id),
            "element_kind": from_kind,
            "element_id": str(from_element_id),
        },
        after_state={
            "unit_id": str(unit_id),
            "element_kind": to_kind,
            "element_id": str(to_element_id),
        },
    )


def unlink_correction_event(
    *,
    tenant_context: TenantContext,
    actor: str,
    unit_id: UUID,
    kind: str,
    element_id: UUID,
) -> AuditEvent:
    """The append-only record of an unlink (the removed binding)."""
    return _draft(
        tenant_context=tenant_context,
        actor=actor,
        action_verb=ACTION_CDD_UNLINK,
        resource_id=str(unit_id),
        before_state={
            "unit_id": str(unit_id),
            "element_kind": kind,
            "element_id": str(element_id),
        },
        after_state={},
    )


__all__ = [
    "ACTION_CDD_RELINK",
    "ACTION_CDD_UNLINK",
    "RESOURCE_TYPE_CDD_EVIDENCE",
    "relink_correction_event",
    "unlink_correction_event",
]
