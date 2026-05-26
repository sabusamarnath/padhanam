"""Draft-audit-event helpers for the intent-classification evaluation runner (D137).

Mirrors ``contexts.retrieval_evaluation.application.audit_events`` per
D110's audit-event-chain regime for platform-computed records. Every
write to the runner's tables emits one ``AuditEvent``; the Postgres
audit adapter overwrites the chain hashes inside the locking
transaction per D37.

The helpers draft events with placeholder chain hashes (GENESIS_HASH
as previous; self-hash recomputed to match the placeholder). The use
case calls ``audit_port.emit(event)``; the adapter overwrites both
hashes with authoritative chain values and returns the persisted
event.

Resource-type strings keep the audit reader's faceted-query surface
faceted on a small canonical set:
- ``intent_classification_evaluation_run`` for run aggregates
  (start + terminal transitions).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from contexts.audit.domain.events import (
    GENESIS_HASH,
    AuditEvent,
    compute_event_hash,
)
from contexts.intent_classification_evaluation.domain.evaluation_run import (
    EvaluationRun,
)
from shared_kernel.tenant_context import TenantContext


RESOURCE_TYPE_RUN: str = "intent_classification_evaluation_run"

ACTION_RUN_START: str = "intent_classification_evaluation.run.start"
ACTION_RUN_COMPLETE: str = "intent_classification_evaluation.run.complete"
ACTION_RUN_FAIL: str = "intent_classification_evaluation.run.fail"


def _draft(
    *,
    tenant_context: TenantContext,
    actor: str,
    action_verb: str,
    resource_id: str,
    before_state: dict[str, Any],
    after_state: dict[str, Any],
    correlation_id: str = "",
) -> AuditEvent:
    """Compose an AuditEvent with placeholder chain hashes.

    The Postgres audit adapter rewrites both hashes inside its
    locking transaction per D37.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    draft_hash = compute_event_hash(
        actor=actor,
        tenant_id=tenant_context.tenant_id,
        jurisdiction=tenant_context.jurisdiction,
        timestamp=timestamp,
        action_verb=action_verb,
        resource_type=RESOURCE_TYPE_RUN,
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
        resource_type=RESOURCE_TYPE_RUN,
        resource_id=resource_id,
        before_state=before_state,
        after_state=after_state,
        correlation_id=correlation_id,
        previous_event_hash=GENESIS_HASH,
        this_event_hash=draft_hash,
    )


def draft_run_start(
    *, tenant_context: TenantContext, run: EvaluationRun, actor: str
) -> AuditEvent:
    """Audit event for the run-start moment."""
    return _draft(
        tenant_context=tenant_context,
        actor=actor,
        action_verb=ACTION_RUN_START,
        resource_id=str(run.id),
        before_state={},
        after_state={
            "gold_set_name": run.gold_set_name,
            "status": run.status.value,
            "model_provider": run.model_identifier.provider.value,
            "model_account": run.model_identifier.account,
            "model_version": run.model_identifier.version,
            "started_at": run.started_at.isoformat(),
        },
    )


def draft_run_complete(
    *, tenant_context: TenantContext, run: EvaluationRun, actor: str
) -> AuditEvent:
    """Audit event for the run-complete moment."""
    assert run.completed_at is not None
    return _draft(
        tenant_context=tenant_context,
        actor=actor,
        action_verb=ACTION_RUN_COMPLETE,
        resource_id=str(run.id),
        before_state={"status": "running"},
        after_state={
            "status": run.status.value,
            "completed_at": run.completed_at.isoformat(),
        },
    )


def draft_run_fail(
    *, tenant_context: TenantContext, run: EvaluationRun, actor: str
) -> AuditEvent:
    """Audit event for the run-fail moment."""
    assert run.completed_at is not None
    return _draft(
        tenant_context=tenant_context,
        actor=actor,
        action_verb=ACTION_RUN_FAIL,
        resource_id=str(run.id),
        before_state={"status": "running"},
        after_state={
            "status": run.status.value,
            "completed_at": run.completed_at.isoformat(),
            "failure_reason": run.failure_reason or "",
        },
    )


__all__ = [
    "ACTION_RUN_COMPLETE",
    "ACTION_RUN_FAIL",
    "ACTION_RUN_START",
    "RESOURCE_TYPE_RUN",
    "draft_run_complete",
    "draft_run_fail",
    "draft_run_start",
]
