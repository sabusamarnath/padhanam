"""In-memory fakes for the four reader ports the EvidenceContext wraps.

Each fake stores rows in a flat list and answers reader queries
respecting tenant scoping and the time-window / status filters the
rules use. Audit and gold-set readers carry stubbed surfaces — they
are passive in Phase 1 rule consumption.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from contexts.retrieval_evaluation.domain import (
    EvaluationAggregate,
    EvaluationRun,
)
from contexts.retrieval_evaluation.domain.query_filters import (
    EvaluationRunListCursor,
)
from contexts.retrieval_evaluation.ports.evaluation_run_reader import (
    EvaluationRunListPage,
    EvaluationRunSnapshot,
)
from contexts.run_history.domain.query_filters import (
    RunListCursor,
    RunListFilters,
)
from contexts.run_history.domain.run_record import RunRecord
from contexts.run_history.ports.reader import RunListPage
from shared_kernel.tenant_context import TenantContext


@dataclass
class FakeEvaluationRunReader:
    """In-memory fake implementing EvaluationRunReader Protocol."""

    runs: list[EvaluationRun] = field(default_factory=list)
    aggregates: dict[UUID, tuple[EvaluationAggregate, ...]] = field(
        default_factory=dict
    )

    async def list_runs(
        self,
        *,
        tenant_context: TenantContext,
        cursor: EvaluationRunListCursor | None,
        page_size: int,
    ) -> EvaluationRunListPage:
        tenant_runs = tuple(
            r for r in self.runs if str(r.tenant_id) == tenant_context.tenant_id
        )
        return EvaluationRunListPage(runs=tenant_runs, next_cursor=None)

    async def get_run_with_results_and_aggregates(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
    ) -> EvaluationRunSnapshot | None:
        match = next(
            (
                r
                for r in self.runs
                if r.id == run_id
                and str(r.tenant_id) == tenant_context.tenant_id
            ),
            None,
        )
        if match is None:
            return None
        return EvaluationRunSnapshot(
            run=match,
            results=(),
            aggregates=self.aggregates.get(run_id, ()),
        )


@dataclass
class FakeRunHistoryReader:
    """In-memory fake implementing RunHistoryReader Protocol."""

    records: list[RunRecord] = field(default_factory=list)

    async def get_run(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
    ) -> RunRecord | None:
        return next(
            (
                r
                for r in self.records
                if r.id == run_id and r.tenant_id == tenant_context.tenant_id
            ),
            None,
        )

    async def list_runs_with_filters(
        self,
        *,
        tenant_context: TenantContext,
        filters: RunListFilters,
        cursor: RunListCursor | None,
    ) -> RunListPage:
        matched: list[RunRecord] = []
        for record in self.records:
            if record.tenant_id != tenant_context.tenant_id:
                continue
            if filters.started_at_range is not None:
                lower, upper = filters.started_at_range
                if not (lower <= record.started_at < upper):
                    continue
            if filters.termination_reasons is not None:
                if record.termination_reason not in filters.termination_reasons:
                    continue
            if filters.agent_template_ids is not None:
                if record.agent_template_id not in filters.agent_template_ids:
                    continue
            matched.append(record)
        return RunListPage(runs=tuple(matched), next_cursor=None)


@dataclass
class FakeGoldSetReader:
    """Passive in-memory fake for the GoldSetReader Protocol.

    Phase 1 rules do not actively query the gold-set reader; the
    fake satisfies the EvidenceContext type contract and raises on
    any actual call.
    """

    async def list_gold_sets(self, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def get_gold_set_with_current_revision(
        self, **kwargs
    ):  # pragma: no cover
        raise NotImplementedError

    async def get_revision_with_entries(self, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def find_current_draft_revision(self, **kwargs):  # pragma: no cover
        raise NotImplementedError


@dataclass
class FakeAuditEventReader:
    """Passive in-memory fake for the AuditEventReader Protocol.

    Phase 1 rules do not actively query audit events; the fake
    satisfies the EvidenceContext type contract and raises on any
    actual call.
    """

    async def get_audit_event(self, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def list_audit_events_with_filters(
        self, **kwargs
    ):  # pragma: no cover
        raise NotImplementedError

    async def verify_chain_segment(self, **kwargs):  # pragma: no cover
        raise NotImplementedError


# ----------------------------------------------------------------------
# Optimization aggregate fakes (commit 5)
# ----------------------------------------------------------------------

from datetime import datetime
from typing import Mapping
from uuid import UUID

from contexts.audit.domain.events import AuditEvent
from contexts.optimization.domain import (
    CategorySkipReason,
    OptimizationRun,
    OptimizationRunStatus,
    Recommendation,
    RecommendationStatusTransition,
)
from contexts.optimization.domain.query_filters import (
    OptimizationRunListCursor,
    RecommendationListCursor,
    RecommendationListFilters,
)
from contexts.optimization.ports.optimization_run_reader import (
    OptimizationRunListPage,
    OptimizationRunSnapshot,
)
from contexts.optimization.ports.recommendation_reader import (
    RecommendationListPage,
)


@dataclass
class FakeOptimizationRunRepository:
    """In-memory fake implementing OptimizationRunRepository."""

    runs: dict[UUID, OptimizationRun] = field(default_factory=dict)

    async def persist_run(
        self,
        *,
        tenant_context: TenantContext,
        run: OptimizationRun,
    ) -> None:
        if run.id in self.runs:
            raise ValueError(f"duplicate optimization run id: {run.id}")
        self.runs[run.id] = run

    async def mark_completed(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
        completed_at: datetime,
        skipped_categories: Mapping[str, CategorySkipReason],
    ) -> None:
        current = self.runs[run_id]
        self.runs[run_id] = OptimizationRun(
            id=current.id,
            tenant_id=current.tenant_id,
            jurisdiction=current.jurisdiction,
            invoked_by_user_id=current.invoked_by_user_id,
            invoked_at=current.invoked_at,
            completed_at=completed_at,
            status=OptimizationRunStatus.COMPLETED,
            skipped_categories=dict(skipped_categories),
        )

    async def mark_failed(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
        completed_at: datetime,
    ) -> None:
        current = self.runs[run_id]
        self.runs[run_id] = OptimizationRun(
            id=current.id,
            tenant_id=current.tenant_id,
            jurisdiction=current.jurisdiction,
            invoked_by_user_id=current.invoked_by_user_id,
            invoked_at=current.invoked_at,
            completed_at=completed_at,
            status=OptimizationRunStatus.FAILED,
            skipped_categories=dict(current.skipped_categories),
        )


@dataclass
class FakeOptimizationRunReader:
    """In-memory fake implementing OptimizationRunReader."""

    repository: FakeOptimizationRunRepository

    async def get_optimization_run(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
    ) -> OptimizationRunSnapshot | None:
        run = self.repository.runs.get(run_id)
        if run is None or str(run.tenant_id) != tenant_context.tenant_id:
            return None
        return OptimizationRunSnapshot(run=run)

    async def list_optimization_runs(
        self,
        *,
        tenant_context: TenantContext,
        cursor: OptimizationRunListCursor | None,
        page_size: int,
    ) -> OptimizationRunListPage:
        tenant_runs = tuple(
            sorted(
                (
                    r
                    for r in self.repository.runs.values()
                    if str(r.tenant_id) == tenant_context.tenant_id
                ),
                key=lambda r: (r.invoked_at, r.id),
                reverse=True,
            )
        )
        return OptimizationRunListPage(runs=tenant_runs, next_cursor=None)


@dataclass
class FakeRecommendationRepository:
    """In-memory fake implementing RecommendationRepository."""

    recommendations: dict[UUID, Recommendation] = field(default_factory=dict)
    transitions: list[RecommendationStatusTransition] = field(
        default_factory=list
    )

    async def persist_recommendation(
        self,
        *,
        tenant_context: TenantContext,
        recommendation: Recommendation,
    ) -> None:
        if recommendation.id in self.recommendations:
            raise ValueError(
                f"duplicate recommendation id: {recommendation.id}"
            )
        self.recommendations[recommendation.id] = recommendation

    async def persist_status_transition(
        self,
        *,
        tenant_context: TenantContext,
        updated_recommendation: Recommendation,
        transition: RecommendationStatusTransition,
    ) -> None:
        if updated_recommendation.id not in self.recommendations:
            raise ValueError(
                f"recommendation {updated_recommendation.id} not present"
            )
        self.recommendations[updated_recommendation.id] = (
            updated_recommendation
        )
        self.transitions.append(transition)


@dataclass
class FakeRecommendationReader:
    """In-memory fake implementing RecommendationReader."""

    repository: FakeRecommendationRepository

    async def get_recommendation(
        self,
        *,
        tenant_context: TenantContext,
        recommendation_id: UUID,
    ) -> Recommendation | None:
        rec = self.repository.recommendations.get(recommendation_id)
        if rec is None or str(rec.tenant_id) != tenant_context.tenant_id:
            return None
        return rec

    async def list_recommendations(
        self,
        *,
        tenant_context: TenantContext,
        filters: RecommendationListFilters,
        cursor: RecommendationListCursor | None,
        page_size: int,
    ) -> RecommendationListPage:
        rows = [
            r
            for r in self.repository.recommendations.values()
            if str(r.tenant_id) == tenant_context.tenant_id
        ]
        if filters.categories is not None:
            rows = [r for r in rows if r.category in filters.categories]
        if filters.statuses is not None:
            rows = [r for r in rows if r.status in filters.statuses]
        rows.sort(key=lambda r: (r.generated_at, r.id), reverse=True)
        return RecommendationListPage(
            recommendations=tuple(rows), next_cursor=None
        )


@dataclass
class RecordingAuditPort:
    """In-memory fake implementing the AuditPort write port."""

    events: list[AuditEvent] = field(default_factory=list)
    fail_on_emit: bool = False

    async def emit(self, event: AuditEvent) -> None:
        if self.fail_on_emit:
            raise RuntimeError("audit emit failed")
        self.events.append(event)
