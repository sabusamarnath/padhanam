"""Draft-audit-event helpers for the portfolio context (D124).

Mirrors the optimization-context audit-event drafting pattern. Per
D110 commitment 7 every portfolio write emits an audit event; the
audit context's existing chain integrity transitively guarantees
tamper-evidence on the portfolio records — there is no parallel
hash chain on the portfolio tables.

The Postgres audit adapter recomputes ``previous_event_hash`` and
``this_event_hash`` inside its locking transaction per D37; the
placeholders here are draft values the adapter overwrites.

Resource types: ``case`` for the aggregate root, ``data_point`` for
DataPoint creation and revision. Action verbs:

- ``portfolio.case.create`` — a Case was created.
- ``portfolio.data_point.create`` — a DataPoint was created.
- ``portfolio.data_point.revise`` — a DataPoint gained a revision.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from contexts.audit.domain.events import (
    GENESIS_HASH,
    AuditEvent,
    compute_event_hash,
)

from contexts.portfolio.domain import Assertion, Case, DataPoint
from shared_kernel import ActorReference, TenantContext

RESOURCE_TYPE_CASE: str = "case"
RESOURCE_TYPE_DATA_POINT: str = "data_point"

ACTION_CASE_CREATE: str = "portfolio.case.create"
ACTION_DATA_POINT_CREATE: str = "portfolio.data_point.create"
ACTION_DATA_POINT_REVISE: str = "portfolio.data_point.revise"


def _draft(
    *,
    tenant_context: TenantContext,
    actor: ActorReference,
    action_verb: str,
    resource_type: str,
    resource_id: str,
    before_state: dict,
    after_state: dict,
    correlation_id: str = "",
) -> AuditEvent:
    timestamp = datetime.now(timezone.utc).isoformat()
    draft_hash = compute_event_hash(
        actor=actor.user_id,
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
        actor=actor.user_id,
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


def draft_case_create(
    *, tenant_context: TenantContext, case: Case, actor: ActorReference
) -> AuditEvent:
    return _draft(
        tenant_context=tenant_context,
        actor=actor,
        action_verb=ACTION_CASE_CREATE,
        resource_type=RESOURCE_TYPE_CASE,
        resource_id=str(case.id),
        before_state={},
        after_state={
            "title": case.title,
            "case_type": case.case_type.value,
            "status": case.status.value,
            "created_at": case.created_at.isoformat(),
            "intake_id": (
                str(case.intake_id) if case.intake_id is not None else None
            ),
        },
    )


def draft_data_point_create(
    *,
    tenant_context: TenantContext,
    data_point: DataPoint,
    actor: ActorReference,
) -> AuditEvent:
    return _draft(
        tenant_context=tenant_context,
        actor=actor,
        action_verb=ACTION_DATA_POINT_CREATE,
        resource_type=RESOURCE_TYPE_DATA_POINT,
        resource_id=str(data_point.id),
        before_state={},
        after_state={
            "case_id": str(data_point.case_id),
            "data_point_type": data_point.data_point_type.value,
            "value": data_point.value,
            "created_at": data_point.created_at.isoformat(),
            "intake_id": (
                str(data_point.assertions[0].intake_id)
                if data_point.assertions[0].intake_id is not None
                else None
            ),
        },
    )


def draft_data_point_revise(
    *,
    tenant_context: TenantContext,
    data_point_id: UUID,
    new_assertion: Assertion,
    actor: ActorReference,
) -> AuditEvent:
    return _draft(
        tenant_context=tenant_context,
        actor=actor,
        action_verb=ACTION_DATA_POINT_REVISE,
        resource_type=RESOURCE_TYPE_DATA_POINT,
        resource_id=str(data_point_id),
        before_state={
            "prior_assertion_id": str(new_assertion.revises_assertion_id)
        },
        after_state={
            "assertion_id": str(new_assertion.id),
            "value": new_assertion.value,
            "created_at": new_assertion.created_at.isoformat(),
            "intake_id": (
                str(new_assertion.intake_id)
                if new_assertion.intake_id is not None
                else None
            ),
        },
    )


__all__ = [
    "ACTION_CASE_CREATE",
    "ACTION_DATA_POINT_CREATE",
    "ACTION_DATA_POINT_REVISE",
    "RESOURCE_TYPE_CASE",
    "RESOURCE_TYPE_DATA_POINT",
    "draft_case_create",
    "draft_data_point_create",
    "draft_data_point_revise",
]
