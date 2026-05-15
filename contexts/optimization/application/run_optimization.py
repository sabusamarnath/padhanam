"""run_optimization engine use case (D111 commitments 2, 5, 8).

Orchestrates one OptimizationRun:

1. Construct ``OptimizationRun`` in ``running`` state; persist; emit
   ``optimization.run.start`` audit event.
2. For each registered ``RecommendationRule``:
   - call ``rule.evaluate(evidence_context=...)``;
   - on success, wrap each ``RecommendationCandidate`` into a
     ``Recommendation`` aggregate (initial ``generated`` state), persist
     each, emit ``optimization.recommendation.generate`` audit event
     carrying the full evidence_citation payload per Finding 4
     disposition;
   - on ``SubstrateGapError``, capture the structured
     ``CategorySkipReason`` on ``skipped_categories`` and continue
     iteration with the next rule.
3. On clean completion: persist ``completed`` status + the
   accumulated ``skipped_categories``; emit
   ``optimization.run.complete`` audit event with the
   ``skipped_categories`` payload embedded.
4. On any uncaught exception: persist ``failed`` status; emit
   ``optimization.run.fail`` audit event; re-raise.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Sequence
from uuid import UUID, uuid4

from contexts.audit.domain.ports import AuditPort

from contexts.optimization.application.audit_events import (
    draft_optimization_run_start,
    draft_optimization_run_terminal,
    draft_recommendation_generate,
)
from contexts.optimization.application.evidence_context import EvidenceContext
from contexts.optimization.domain import (
    CategorySkipReason,
    OptimizationRun,
    OptimizationRunStatus,
    Recommendation,
    RecommendationCandidate,
    RecommendationRule,
    RecommendationStatus,
    SubstrateGapError,
)
from contexts.optimization.ports.optimization_run_repository import (
    OptimizationRunRepository,
)
from contexts.optimization.ports.recommendation_repository import (
    RecommendationRepository,
)
from shared_kernel.tenant_context import TenantContext


@dataclass(frozen=True)
class RunOptimizationResult:
    """Engine-run summary returned to the CLI."""

    run: OptimizationRun
    recommendations: tuple[Recommendation, ...]
    skipped_categories: Mapping[str, CategorySkipReason]


async def run_optimization(
    *,
    tenant_context: TenantContext,
    invoked_by_user_id: str,
    rules: Sequence[RecommendationRule],
    evidence_context: EvidenceContext,
    optimization_run_repository: OptimizationRunRepository,
    recommendation_repository: RecommendationRepository,
    audit_port: AuditPort,
    now: datetime | None = None,
    run_id: UUID | None = None,
) -> RunOptimizationResult:
    invoked_at = now or datetime.now(timezone.utc)
    run_uuid = run_id or uuid4()
    run = OptimizationRun(
        id=run_uuid,
        tenant_id=UUID(tenant_context.tenant_id),
        jurisdiction=tenant_context.jurisdiction,
        invoked_by_user_id=invoked_by_user_id,
        invoked_at=invoked_at,
        completed_at=None,
        status=OptimizationRunStatus.RUNNING,
    )
    await optimization_run_repository.persist_run(
        tenant_context=tenant_context, run=run
    )
    await audit_port.emit(
        draft_optimization_run_start(
            tenant_context=tenant_context, run=run
        )
    )

    skipped: dict[str, CategorySkipReason] = {}
    persisted_recommendations: list[Recommendation] = []

    try:
        for rule in rules:
            try:
                candidates = await rule.evaluate(
                    evidence_context=evidence_context
                )
            except SubstrateGapError as exc:
                skipped[exc.category.value] = exc.reason
                continue
            for candidate in candidates:
                recommendation = _build_recommendation(
                    candidate=candidate,
                    tenant_context=tenant_context,
                    generated_by_run_id=run.id,
                    generated_at=invoked_at,
                )
                await recommendation_repository.persist_recommendation(
                    tenant_context=tenant_context,
                    recommendation=recommendation,
                )
                await audit_port.emit(
                    draft_recommendation_generate(
                        tenant_context=tenant_context,
                        recommendation=recommendation,
                        actor=invoked_by_user_id,
                    )
                )
                persisted_recommendations.append(recommendation)

        completed_at = datetime.now(timezone.utc)
        await optimization_run_repository.mark_completed(
            tenant_context=tenant_context,
            run_id=run.id,
            completed_at=completed_at,
            skipped_categories=skipped,
        )
        completed_run = OptimizationRun(
            id=run.id,
            tenant_id=run.tenant_id,
            jurisdiction=run.jurisdiction,
            invoked_by_user_id=run.invoked_by_user_id,
            invoked_at=run.invoked_at,
            completed_at=completed_at,
            status=OptimizationRunStatus.COMPLETED,
            skipped_categories=skipped,
        )
        await audit_port.emit(
            draft_optimization_run_terminal(
                tenant_context=tenant_context,
                run=completed_run,
                completed_at=completed_at,
                new_status="completed",
                skipped_categories=skipped,
            )
        )
        return RunOptimizationResult(
            run=completed_run,
            recommendations=tuple(persisted_recommendations),
            skipped_categories=skipped,
        )
    except Exception:
        failed_at = datetime.now(timezone.utc)
        await optimization_run_repository.mark_failed(
            tenant_context=tenant_context,
            run_id=run.id,
            completed_at=failed_at,
        )
        failed_run = OptimizationRun(
            id=run.id,
            tenant_id=run.tenant_id,
            jurisdiction=run.jurisdiction,
            invoked_by_user_id=run.invoked_by_user_id,
            invoked_at=run.invoked_at,
            completed_at=failed_at,
            status=OptimizationRunStatus.FAILED,
            skipped_categories=skipped,
        )
        await audit_port.emit(
            draft_optimization_run_terminal(
                tenant_context=tenant_context,
                run=failed_run,
                completed_at=failed_at,
                new_status="failed",
                skipped_categories=skipped,
            )
        )
        raise


def _build_recommendation(
    *,
    candidate: RecommendationCandidate,
    tenant_context: TenantContext,
    generated_by_run_id: UUID,
    generated_at: datetime,
) -> Recommendation:
    return Recommendation(
        id=uuid4(),
        tenant_id=UUID(tenant_context.tenant_id),
        jurisdiction=tenant_context.jurisdiction,
        category=candidate.category,
        subject=candidate.subject,
        text=candidate.text,
        evidence_citations=candidate.evidence_citations,
        status=RecommendationStatus.GENERATED,
        generated_at=generated_at,
        generated_by_run_id=generated_by_run_id,
        last_transition_at=generated_at,
        last_transition_by_user_id=None,
    )


__all__ = [
    "RunOptimizationResult",
    "run_optimization",
]
