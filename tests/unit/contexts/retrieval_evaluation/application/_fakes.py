"""In-memory fakes of the GoldSetRepository and GoldSetReader ports.

The fakes keep gold sets, revisions, and entries in dicts keyed by
id so use-case tests exercise the full authoring lifecycle without
a Postgres dependency. Tenant scoping is enforced at every method
to mirror the Postgres adapter's tenant_isolation contract.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from uuid import UUID

from shared_kernel.tenant_context import TenantContext

from contexts.retrieval_evaluation.domain import (
    GoldSet,
    GoldSetEntry,
    GoldSetRevision,
    GoldSetRevisionStatus,
)
from contexts.retrieval_evaluation.domain.query_filters import (
    GoldSetListCursor,
)
from contexts.retrieval_evaluation.ports.reader import (
    GoldSetListPage,
    GoldSetWithCurrentRevision,
    RevisionWithEntries,
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
