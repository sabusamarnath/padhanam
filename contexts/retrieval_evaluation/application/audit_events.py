"""Draft-audit-event helpers for the retrieval-evaluation runner (D110 commitment 7).

Mirrors the ``_draft_event`` helper at
``contexts/agent/adapters/outbound/agent_loop_executor.py`` per the
audit-context-event-level tamper-evidence absorption commitment.

Per D110 commitment 7 and its three-regime distinction in the
reasoning paragraph, the runner's three record families
(``evaluation_runs``, ``evaluation_results``, ``evaluation_aggregates``)
sit under the audit-event-chain regime as platform-computed records.
Every write to those tables emits one ``AuditEvent``; the Postgres
audit adapter is the chain authority and recomputes the
``previous_event_hash`` and ``this_event_hash`` values inside its
locking transaction per D37.

The helpers below draft events with placeholder chain hashes
(``GENESIS_HASH`` as the previous-event-hash, self-hash recomputed
to match the placeholder). The application use case calls
``audit_port.emit(event)``; the adapter overwrites both hashes with
authoritative chain values and returns the persisted event.

Resource-type strings keep the audit reader's faceted-query surface
faceted on a small canonical set:

- ``evaluation_run`` for run aggregates (start + terminal-transition).
- ``evaluation_result`` for per-query result rows.
- ``evaluation_aggregate`` for per-strategy aggregate rows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from contexts.audit.domain.events import (
    GENESIS_HASH,
    AuditEvent,
    compute_event_hash,
)

from shared_kernel.tenant_context import TenantContext

from contexts.retrieval_evaluation.domain import (
    EvaluationAggregate,
    EvaluationResult,
    EvaluationRun,
)


RESOURCE_TYPE_RUN: str = "evaluation_run"
RESOURCE_TYPE_RESULT: str = "evaluation_result"
RESOURCE_TYPE_AGGREGATE: str = "evaluation_aggregate"

ACTION_RUN_START: str = "retrieval_evaluation.run.start"
ACTION_RUN_COMPLETE: str = "retrieval_evaluation.run.complete"
ACTION_RUN_FAIL: str = "retrieval_evaluation.run.fail"
ACTION_RESULT_APPEND: str = "retrieval_evaluation.result.append"
ACTION_AGGREGATE_APPEND: str = "retrieval_evaluation.aggregate.append"


def _draft(
    *,
    tenant_context: TenantContext,
    actor: str,
    action_verb: str,
    resource_type: str,
    resource_id: str,
    before_state: dict[str, Any],
    after_state: dict[str, Any],
    correlation_id: str = "",
) -> AuditEvent:
    """Compose an AuditEvent with placeholder chain hashes.

    The Postgres audit adapter rewrites both hashes inside its
    locking transaction per D37; the placeholders here are draft
    values the adapter overwrites.
    """
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


def draft_run_start(
    *,
    tenant_context: TenantContext,
    run: EvaluationRun,
) -> AuditEvent:
    return _draft(
        tenant_context=tenant_context,
        actor=run.invoked_by_user_id,
        action_verb=ACTION_RUN_START,
        resource_type=RESOURCE_TYPE_RUN,
        resource_id=str(run.id),
        before_state={},
        after_state={
            "gold_set_id": str(run.gold_set_id),
            "gold_set_revision_id": str(run.gold_set_revision_id),
            "invoked_at": run.invoked_at.isoformat(),
            "status": run.status.value,
        },
    )


def draft_run_terminal(
    *,
    tenant_context: TenantContext,
    run: EvaluationRun,
    completed_at: datetime,
    new_status: str,
) -> AuditEvent:
    action_verb = (
        ACTION_RUN_COMPLETE if new_status == "completed" else ACTION_RUN_FAIL
    )
    return _draft(
        tenant_context=tenant_context,
        actor=run.invoked_by_user_id,
        action_verb=action_verb,
        resource_type=RESOURCE_TYPE_RUN,
        resource_id=str(run.id),
        before_state={"status": "running"},
        after_state={
            "status": new_status,
            "completed_at": completed_at.isoformat(),
        },
    )


def draft_result_append(
    *,
    tenant_context: TenantContext,
    run: EvaluationRun,
    result: EvaluationResult,
) -> AuditEvent:
    return _draft(
        tenant_context=tenant_context,
        actor=run.invoked_by_user_id,
        action_verb=ACTION_RESULT_APPEND,
        resource_type=RESOURCE_TYPE_RESULT,
        resource_id=str(result.id),
        before_state={},
        after_state={
            "evaluation_run_id": str(result.evaluation_run_id),
            "gold_set_entry_id": str(result.gold_set_entry_id),
            "retrieval_strategy": result.retrieval_strategy,
            "mrr": str(result.mrr),
            "latency_ms": result.latency_ms,
            "returned_chunk_count": len(result.returned_chunk_ids),
        },
    )


def draft_aggregate_append(
    *,
    tenant_context: TenantContext,
    run: EvaluationRun,
    aggregate: EvaluationAggregate,
) -> AuditEvent:
    return _draft(
        tenant_context=tenant_context,
        actor=run.invoked_by_user_id,
        action_verb=ACTION_AGGREGATE_APPEND,
        resource_type=RESOURCE_TYPE_AGGREGATE,
        resource_id=str(aggregate.id),
        before_state={},
        after_state={
            "evaluation_run_id": str(aggregate.evaluation_run_id),
            "retrieval_strategy": aggregate.retrieval_strategy,
            "mrr_mean": str(aggregate.mrr_mean),
            "latency_ms_p50": aggregate.latency_ms_p50,
            "latency_ms_p95": aggregate.latency_ms_p95,
            "latency_ms_mean": aggregate.latency_ms_mean,
        },
    )


def _coerce_decimal(value: Any) -> Decimal:
    """Stable Decimal coercion guarding against float-roundtrip surprise."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


__all__ = [
    "ACTION_AGGREGATE_APPEND",
    "ACTION_RESULT_APPEND",
    "ACTION_RUN_COMPLETE",
    "ACTION_RUN_FAIL",
    "ACTION_RUN_START",
    "RESOURCE_TYPE_AGGREGATE",
    "RESOURCE_TYPE_RESULT",
    "RESOURCE_TYPE_RUN",
    "draft_aggregate_append",
    "draft_result_append",
    "draft_run_start",
    "draft_run_terminal",
]
