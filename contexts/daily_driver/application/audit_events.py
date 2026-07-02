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

# Warming steps (S103v, D224): a warming action against a contact or a lead, stored
# as an append-only audit event and read back per subject via the faceted reader.
ACTION_WARMING_STEP: str = "warming.step"
# A general per-opportunity activity (S103w, D229) — the union of this + warming.step
# is the opportunity's append-only history; an entry may name a qualification field it
# touched, bumping that field's last_touched.
ACTION_OPPORTUNITY_ACTIVITY: str = "opportunity.activity"
RESOURCE_TYPE_CONTACT: str = "contact"
RESOURCE_TYPE_OPPORTUNITY: str = "opportunity"
WARMING_STEP_KINDS: tuple[str, ...] = (
    "intro_requested", "follow_up_sent", "referral_asked", "message_sent",
)


def _draft(
    *,
    tenant_context: TenantContext,
    actor: str,
    action_verb: str,
    resource_id: str,
    before_state: dict,
    after_state: dict,
    resource_type: str = RESOURCE_TYPE_CDD_EVIDENCE,
    correlation_id: str = "",
) -> AuditEvent:
    timestamp = datetime.now(timezone.utc).isoformat()
    draft_hash = compute_event_hash(
        actor=actor,
        tenant_id=tenant_context.tenant_id,
        jurisdiction=tenant_context.jurisdiction,
        timestamp=timestamp,
        action_verb=action_verb,
        resource_type=resource_type,
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
        resource_type=resource_type,
        resource_id=resource_id,
        before_state=before_state,
        after_state=after_state,
        correlation_id=correlation_id,
        previous_event_hash=GENESIS_HASH,
        this_event_hash=draft_hash,
    )


def warming_step_event(
    *,
    tenant_context: TenantContext,
    actor: str,
    subject_type: str,
    subject_id: UUID,
    kind: str,
    note: str = "",
) -> AuditEvent:
    """The append-only record of a warming step (D224) — a state change on tenant
    data, so the compliance log and the future warming-learning signal are the same
    hash-chained artefact. ``subject_type`` is ``contact`` or ``opportunity``."""
    return _draft(
        tenant_context=tenant_context,
        actor=actor,
        action_verb=ACTION_WARMING_STEP,
        resource_type=subject_type,
        resource_id=str(subject_id),
        before_state={},
        after_state={"kind": kind, "note": note, "subject_type": subject_type},
    )


def opportunity_activity_event(
    *,
    tenant_context: TenantContext,
    actor: str,
    opportunity_id: UUID,
    kind: str,
    note: str = "",
    touches_field: str | None = None,
) -> AuditEvent:
    """The append-only record of a general opportunity activity (D229). ``kind`` is a
    short label (e.g. call, email, applied, interview); ``touches_field`` names a
    qualification field the activity refreshed (bumped separately by the use case)."""
    return _draft(
        tenant_context=tenant_context,
        actor=actor,
        action_verb=ACTION_OPPORTUNITY_ACTIVITY,
        resource_type=RESOURCE_TYPE_OPPORTUNITY,
        resource_id=str(opportunity_id),
        before_state={},
        after_state={"kind": kind, "note": note, "touches_field": touches_field or ""},
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
    "ACTION_OPPORTUNITY_ACTIVITY",
    "ACTION_WARMING_STEP",
    "RESOURCE_TYPE_CDD_EVIDENCE",
    "RESOURCE_TYPE_CONTACT",
    "RESOURCE_TYPE_OPPORTUNITY",
    "WARMING_STEP_KINDS",
    "opportunity_activity_event",
    "relink_correction_event",
    "unlink_correction_event",
    "warming_step_event",
]
