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
