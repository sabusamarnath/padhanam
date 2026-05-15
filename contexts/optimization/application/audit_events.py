"""Draft-audit-event helpers for the optimization engine (D111 cmt 8).

Mirrors the retrieval-evaluation runner's audit-event drafting
pattern. Per D111 commitment 8 the optimization-run lifecycle plus
the recommendation lifecycle both emit audit events; the audit
context's existing chain integrity transitively guarantees tamper-
evidence on the optimization-context records.

The Postgres audit adapter recomputes ``previous_event_hash`` and
``this_event_hash`` inside its locking transaction per D37; the
placeholders here are draft values the adapter overwrites.

Resource-type strings keep the audit reader's faceted-query surface
faceted on a small canonical set:

- ``optimization_run`` for engine-invocation aggregates.
- ``recommendation`` for generation + lifecycle transitions.

Action verbs:

- ``optimization.run.start`` — engine invocation begin.
- ``optimization.run.complete`` — engine invocation finished cleanly.
- ``optimization.run.fail`` — engine invocation aborted on exception.
- ``optimization.recommendation.generate`` — initial-state row write.
- ``optimization.recommendation.acknowledge`` — user acknowledged.
- ``optimization.recommendation.apply`` — user committed to apply.
- ``optimization.recommendation.reject`` — user dismissed.

Per Finding 4 disposition, the full evidence_citation payload is
embedded in the audit event ``after_state`` at generation AND at
every status transition. Multiple chain-anchoring points for the
same citation strengthen procurement-grade defence against
tampering with the recommendations table directly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from contexts.audit.domain.events import (
    GENESIS_HASH,
    AuditEvent,
    compute_event_hash,
)

from contexts.optimization.domain import (
    CategorySkipReason,
    OptimizationRun,
    Recommendation,
    RecommendationStatus,
)
from contexts.optimization.domain.citation_serialization import (
    citations_to_payload,
    skipped_categories_to_dict,
)
from shared_kernel.tenant_context import TenantContext


RESOURCE_TYPE_OPTIMIZATION_RUN: str = "optimization_run"
RESOURCE_TYPE_RECOMMENDATION: str = "recommendation"

ACTION_OPTIMIZATION_RUN_START: str = "optimization.run.start"
ACTION_OPTIMIZATION_RUN_COMPLETE: str = "optimization.run.complete"
ACTION_OPTIMIZATION_RUN_FAIL: str = "optimization.run.fail"

ACTION_RECOMMENDATION_GENERATE: str = "optimization.recommendation.generate"
ACTION_RECOMMENDATION_ACKNOWLEDGE: str = (
    "optimization.recommendation.acknowledge"
)
ACTION_RECOMMENDATION_APPLY: str = "optimization.recommendation.apply"
ACTION_RECOMMENDATION_REJECT: str = "optimization.recommendation.reject"


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


def draft_optimization_run_start(
    *,
    tenant_context: TenantContext,
    run: OptimizationRun,
) -> AuditEvent:
    return _draft(
        tenant_context=tenant_context,
        actor=run.invoked_by_user_id,
        action_verb=ACTION_OPTIMIZATION_RUN_START,
        resource_type=RESOURCE_TYPE_OPTIMIZATION_RUN,
        resource_id=str(run.id),
        before_state={},
        after_state={
            "invoked_at": run.invoked_at.isoformat(),
            "status": run.status.value,
        },
    )


def draft_optimization_run_terminal(
    *,
    tenant_context: TenantContext,
    run: OptimizationRun,
    completed_at: datetime,
    new_status: str,
    skipped_categories: Mapping[str, CategorySkipReason],
) -> AuditEvent:
    action_verb = (
        ACTION_OPTIMIZATION_RUN_COMPLETE
        if new_status == "completed"
        else ACTION_OPTIMIZATION_RUN_FAIL
    )
    return _draft(
        tenant_context=tenant_context,
        actor=run.invoked_by_user_id,
        action_verb=action_verb,
        resource_type=RESOURCE_TYPE_OPTIMIZATION_RUN,
        resource_id=str(run.id),
        before_state={"status": "running"},
        after_state={
            "status": new_status,
            "completed_at": completed_at.isoformat(),
            "skipped_categories": skipped_categories_to_dict(
                skipped_categories
            ),
        },
    )


def draft_recommendation_generate(
    *,
    tenant_context: TenantContext,
    recommendation: Recommendation,
    actor: str,
) -> AuditEvent:
    return _draft(
        tenant_context=tenant_context,
        actor=actor,
        action_verb=ACTION_RECOMMENDATION_GENERATE,
        resource_type=RESOURCE_TYPE_RECOMMENDATION,
        resource_id=str(recommendation.id),
        before_state={},
        after_state={
            "category": recommendation.category.value,
            "subject": recommendation.subject,
            "text": recommendation.text,
            "status": recommendation.status.value,
            "generated_by_run_id": str(recommendation.generated_by_run_id),
            "evidence_citations": citations_to_payload(
                recommendation.evidence_citations
            ),
        },
    )


def draft_recommendation_transition(
    *,
    tenant_context: TenantContext,
    recommendation: Recommendation,
    actor: str,
    from_status: RecommendationStatus,
) -> AuditEvent:
    if recommendation.status is RecommendationStatus.ACKNOWLEDGED:
        action_verb = ACTION_RECOMMENDATION_ACKNOWLEDGE
    elif recommendation.status is RecommendationStatus.APPLIED:
        action_verb = ACTION_RECOMMENDATION_APPLY
    elif recommendation.status is RecommendationStatus.REJECTED:
        action_verb = ACTION_RECOMMENDATION_REJECT
    else:  # pragma: no cover - defensive; transitions cannot target generated
        raise ValueError(
            f"unexpected transition target status: "
            f"{recommendation.status.value}"
        )
    return _draft(
        tenant_context=tenant_context,
        actor=actor,
        action_verb=action_verb,
        resource_type=RESOURCE_TYPE_RECOMMENDATION,
        resource_id=str(recommendation.id),
        before_state={"status": from_status.value},
        after_state={
            "status": recommendation.status.value,
            "category": recommendation.category.value,
            "evidence_citations": citations_to_payload(
                recommendation.evidence_citations
            ),
        },
    )


__all__ = [
    "ACTION_OPTIMIZATION_RUN_COMPLETE",
    "ACTION_OPTIMIZATION_RUN_FAIL",
    "ACTION_OPTIMIZATION_RUN_START",
    "ACTION_RECOMMENDATION_ACKNOWLEDGE",
    "ACTION_RECOMMENDATION_APPLY",
    "ACTION_RECOMMENDATION_GENERATE",
    "ACTION_RECOMMENDATION_REJECT",
    "RESOURCE_TYPE_OPTIMIZATION_RUN",
    "RESOURCE_TYPE_RECOMMENDATION",
    "draft_optimization_run_start",
    "draft_optimization_run_terminal",
    "draft_recommendation_generate",
    "draft_recommendation_transition",
]
