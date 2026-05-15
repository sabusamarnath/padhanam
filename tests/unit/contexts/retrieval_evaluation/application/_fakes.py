"""In-memory fakes of the retrieval-evaluation ports.

Gold-set side (D109): ``FakeGoldSetRepository``, ``FakeGoldSetReader``
backed by ``InMemoryGoldSetStore``.

Runner side (D110, S40): ``FakeEvaluationRunRepository``,
``FakeEvaluationRunReader`` backed by ``InMemoryEvaluationRunStore``;
``FakeRetrievalRunner`` programmable to return canned chunk IDs and
latency per (query, strategy_dispatch); ``RecordingAuditPort`` records
emitted events for assertion.

All fakes enforce tenant scoping at every method to mirror the
Postgres adapters' tenant_isolation contract.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any, Callable, Mapping
from uuid import UUID

from contexts.audit.domain.events import AuditEvent

from shared_kernel.tenant_context import TenantContext

from contexts.retrieval_evaluation.domain import (
    EvaluationAggregate,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunStatus,
    GoldSet,
    GoldSetEntry,
    GoldSetRevision,
    GoldSetRevisionStatus,
)
from contexts.retrieval_evaluation.domain.query_filters import (
    EvaluationRunListCursor,
    GoldSetListCursor,
)
from contexts.retrieval_evaluation.ports.evaluation_run_reader import (
    EvaluationRunListPage,
    EvaluationRunSnapshot,
)
from contexts.retrieval_evaluation.ports.reader import (
    GoldSetListPage,
    GoldSetWithCurrentRevision,
    RevisionWithEntries,
)
from contexts.retrieval_evaluation.ports.retrieval_runner import (
    RankedChunks,
)


class InMemoryGoldSetStore:
    """Backing storage shared by FakeRepository and FakeReader."""

    def __init__(self) -> None:
        self.gold_sets: dict[UUID, GoldSet] = {}
        self.revisions: dict[UUID, GoldSetRevision] = {}
        self.entries: dict[UUID, GoldSetEntry] = {}

    def _tenant_match(self, tenant_context: TenantContext, gold_set: GoldSet) -> bool:
        return str(gold_set.tenant_id) == tenant_context.tenant_id


class FakeGoldSetRepository:
    def __init__(self, store: InMemoryGoldSetStore) -> None:
        self._store = store

    async def persist_new_gold_set(
        self,
        *,
        tenant_context: TenantContext,
        gold_set: GoldSet,
        initial_revision: GoldSetRevision,
    ) -> None:
        self._store.gold_sets[gold_set.id] = gold_set
        self._store.revisions[initial_revision.id] = initial_revision

    async def open_new_draft_revision(
        self,
        *,
        tenant_context: TenantContext,
        revision: GoldSetRevision,
    ) -> None:
        gold_set = self._store.gold_sets[revision.gold_set_id]
        if not self._store._tenant_match(tenant_context, gold_set):
            raise PermissionError("cross-tenant write")
        self._store.revisions[revision.id] = revision

    async def append_entry(
        self,
        *,
        tenant_context: TenantContext,
        entry: GoldSetEntry,
    ) -> None:
        revision = self._store.revisions[entry.gold_set_revision_id]
        if revision.status is not GoldSetRevisionStatus.DRAFT:
            raise PermissionError("cannot append to finalized revision")
        gold_set = self._store.gold_sets[revision.gold_set_id]
        if not self._store._tenant_match(tenant_context, gold_set):
            raise PermissionError("cross-tenant write")
        self._store.entries[entry.id] = entry

    async def finalize_revision(
        self,
        *,
        tenant_context: TenantContext,
        revision_id: UUID,
        gold_set_id: UUID,
        this_event_hash: str,
        previous_event_hash: str,
        finalized_at: datetime,
    ) -> None:
        revision = self._store.revisions[revision_id]
        if revision.status is not GoldSetRevisionStatus.DRAFT:
            raise PermissionError("revision is not draft")
        gold_set = self._store.gold_sets[gold_set_id]
        if not self._store._tenant_match(tenant_context, gold_set):
            raise PermissionError("cross-tenant write")
        self._store.revisions[revision_id] = replace(
            revision,
            status=GoldSetRevisionStatus.FINALIZED,
            finalized_at=finalized_at,
            this_event_hash=this_event_hash,
            previous_event_hash=previous_event_hash,
        )
        self._store.gold_sets[gold_set_id] = replace(
            gold_set,
            current_revision_id=revision_id,
        )


class FakeGoldSetReader:
    def __init__(self, store: InMemoryGoldSetStore) -> None:
        self._store = store

    async def list_gold_sets(
        self,
        *,
        tenant_context: TenantContext,
        cursor: GoldSetListCursor | None,
        page_size: int,
    ) -> GoldSetListPage:
        rows = [
            gs
            for gs in self._store.gold_sets.values()
            if self._store._tenant_match(tenant_context, gs)
        ]
        rows.sort(key=lambda gs: (gs.created_at, gs.id), reverse=True)
        if cursor is not None:
            rows = [
                gs
                for gs in rows
                if (gs.created_at, gs.id) < (cursor.created_at, cursor.id)
            ]
        page_rows = tuple(rows[:page_size])
        next_cursor: GoldSetListCursor | None = None
        if len(rows) > page_size:
            last = page_rows[-1]
            next_cursor = GoldSetListCursor(
                created_at=last.created_at,
                id=last.id,
                page_size=page_size,
            )
        return GoldSetListPage(gold_sets=page_rows, next_cursor=next_cursor)

    async def get_gold_set_with_current_revision(
        self,
        *,
        tenant_context: TenantContext,
        gold_set_id: UUID,
    ) -> GoldSetWithCurrentRevision | None:
        gold_set = self._store.gold_sets.get(gold_set_id)
        if gold_set is None or not self._store._tenant_match(
            tenant_context, gold_set
        ):
            return None
        current_revision: GoldSetRevision | None = None
        entries: tuple[GoldSetEntry, ...] = ()
        if gold_set.current_revision_id is not None:
            current_revision = self._store.revisions.get(
                gold_set.current_revision_id
            )
            if current_revision is not None:
                entries = tuple(
                    sorted(
                        (
                            e
                            for e in self._store.entries.values()
                            if e.gold_set_revision_id == current_revision.id
                        ),
                        key=lambda e: e.entry_index,
                    )
                )
        return GoldSetWithCurrentRevision(
            gold_set=gold_set,
            current_revision=current_revision,
            entries=entries,
        )

    async def get_revision_with_entries(
        self,
        *,
        tenant_context: TenantContext,
        revision_id: UUID,
    ) -> RevisionWithEntries | None:
        revision = self._store.revisions.get(revision_id)
        if revision is None:
            return None
        gold_set = self._store.gold_sets.get(revision.gold_set_id)
        if gold_set is None or not self._store._tenant_match(
            tenant_context, gold_set
        ):
            return None
        entries = tuple(
            sorted(
                (
                    e
                    for e in self._store.entries.values()
                    if e.gold_set_revision_id == revision_id
                ),
                key=lambda e: e.entry_index,
            )
        )
        return RevisionWithEntries(revision=revision, entries=entries)

    async def find_current_draft_revision(
        self,
        *,
        tenant_context: TenantContext,
        gold_set_id: UUID,
    ) -> GoldSetRevision | None:
        gold_set = self._store.gold_sets.get(gold_set_id)
        if gold_set is None or not self._store._tenant_match(
            tenant_context, gold_set
        ):
            return None
        drafts = [
            rev
            for rev in self._store.revisions.values()
            if rev.gold_set_id == gold_set_id
            and rev.status is GoldSetRevisionStatus.DRAFT
        ]
        if not drafts:
            return None
        drafts.sort(key=lambda r: r.revision_number, reverse=True)
        return drafts[0]


# ----------------------------------------------------------------------
# Runner-side fakes (D110, S40)
# ----------------------------------------------------------------------


class InMemoryEvaluationRunStore:
    """Backing storage shared by FakeEvaluationRunRepository/Reader."""

    def __init__(self) -> None:
        self.runs: dict[UUID, EvaluationRun] = {}
        self.results: dict[UUID, EvaluationResult] = {}
        self.aggregates: dict[UUID, EvaluationAggregate] = {}

    def _tenant_match(
        self, tenant_context: TenantContext, run: EvaluationRun
    ) -> bool:
        return str(run.tenant_id) == tenant_context.tenant_id


class FakeEvaluationRunRepository:
    def __init__(self, store: InMemoryEvaluationRunStore) -> None:
        self._store = store

    async def persist_run(
        self,
        *,
        tenant_context: TenantContext,
        run: EvaluationRun,
    ) -> None:
        if str(run.tenant_id) != tenant_context.tenant_id:
            raise PermissionError("cross-tenant write")
        self._store.runs[run.id] = run

    async def persist_result(
        self,
        *,
        tenant_context: TenantContext,
        result: EvaluationResult,
    ) -> None:
        parent = self._store.runs.get(result.evaluation_run_id)
        if parent is None or not self._store._tenant_match(
            tenant_context, parent
        ):
            raise PermissionError("cross-tenant or orphan result")
        self._store.results[result.id] = result

    async def persist_aggregate(
        self,
        *,
        tenant_context: TenantContext,
        aggregate: EvaluationAggregate,
    ) -> None:
        parent = self._store.runs.get(aggregate.evaluation_run_id)
        if parent is None or not self._store._tenant_match(
            tenant_context, parent
        ):
            raise PermissionError("cross-tenant or orphan aggregate")
        self._store.aggregates[aggregate.id] = aggregate

    async def mark_completed(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
        completed_at: datetime,
    ) -> None:
        run = self._store.runs[run_id]
        if not self._store._tenant_match(tenant_context, run):
            raise PermissionError("cross-tenant transition")
        self._store.runs[run_id] = replace(
            run,
            status=EvaluationRunStatus.COMPLETED,
            completed_at=completed_at,
        )

    async def mark_failed(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
        completed_at: datetime,
    ) -> None:
        run = self._store.runs[run_id]
        if not self._store._tenant_match(tenant_context, run):
            raise PermissionError("cross-tenant transition")
        self._store.runs[run_id] = replace(
            run,
            status=EvaluationRunStatus.FAILED,
            completed_at=completed_at,
        )


class FakeEvaluationRunReader:
    def __init__(self, store: InMemoryEvaluationRunStore) -> None:
        self._store = store

    async def list_runs(
        self,
        *,
        tenant_context: TenantContext,
        cursor: EvaluationRunListCursor | None,
        page_size: int,
    ) -> EvaluationRunListPage:
        rows = [
            r
            for r in self._store.runs.values()
            if self._store._tenant_match(tenant_context, r)
        ]
        rows.sort(key=lambda r: (r.invoked_at, r.id), reverse=True)
        if cursor is not None:
            rows = [
                r
                for r in rows
                if (r.invoked_at, r.id) < (cursor.invoked_at, cursor.id)
            ]
        page_rows = tuple(rows[:page_size])
        next_cursor: EvaluationRunListCursor | None = None
        if len(rows) > page_size:
            last = page_rows[-1]
            next_cursor = EvaluationRunListCursor(
                invoked_at=last.invoked_at,
                id=last.id,
                page_size=page_size,
            )
        return EvaluationRunListPage(runs=page_rows, next_cursor=next_cursor)

    async def get_run_with_results_and_aggregates(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
    ) -> EvaluationRunSnapshot | None:
        run = self._store.runs.get(run_id)
        if run is None or not self._store._tenant_match(tenant_context, run):
            return None
        results = tuple(
            sorted(
                (
                    r
                    for r in self._store.results.values()
                    if r.evaluation_run_id == run_id
                ),
                key=lambda r: (str(r.gold_set_entry_id), r.retrieval_strategy),
            )
        )
        aggregates = tuple(
            sorted(
                (
                    a
                    for a in self._store.aggregates.values()
                    if a.evaluation_run_id == run_id
                ),
                key=lambda a: a.retrieval_strategy,
            )
        )
        return EvaluationRunSnapshot(
            run=run, results=results, aggregates=aggregates
        )


class FakeRetrievalRunner:
    """Programmable RetrievalRunnerPort fake.

    ``responses`` maps (query, frozenset of strategy_dispatch items) →
    ``RankedChunks``; lookup misses return an empty RankedChunks unless
    ``raise_on_miss`` is set, in which case the configured exception
    fires (useful for failure-path tests).
    """

    def __init__(
        self,
        *,
        responses: dict[tuple[str, frozenset], RankedChunks] | None = None,
        raise_on_miss: BaseException | None = None,
        always_raises: BaseException | None = None,
    ) -> None:
        self._responses = responses or {}
        self._raise_on_miss = raise_on_miss
        self._always_raises = always_raises
        self.invocations: list[
            tuple[str, Mapping[str, Any], int]
        ] = []

    async def __call__(
        self,
        *,
        query: str,
        tenant_context: TenantContext,
        strategy_dispatch: Mapping[str, Any],
        top_k: int,
    ) -> RankedChunks:
        self.invocations.append((query, dict(strategy_dispatch), top_k))
        if self._always_raises is not None:
            raise self._always_raises
        key = (query, frozenset(strategy_dispatch.items()))
        if key in self._responses:
            return self._responses[key]
        if self._raise_on_miss is not None:
            raise self._raise_on_miss
        return RankedChunks(chunk_ids=(), latency_ms=0)


class RecordingAuditPort:
    """In-memory AuditPort that records emitted events."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def emit(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        return event

    async def verify_chain(self, tenant_id):  # pragma: no cover — unused at runner tests
        raise NotImplementedError
