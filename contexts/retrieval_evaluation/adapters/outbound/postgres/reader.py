"""Postgres adapter for GoldSetReader (D109; S39 commit 5).

Implements ``GoldSetReader`` against per-tenant Postgres data planes.
Mirrors the run_history reader pattern from S33: per-tenant session-
factory resolver, bound tenant-id defence-in-depth, sqlalchemy 2.0
Core for row materialisation.

Tenant-isolation contract: every read validates the incoming
``TenantContext.tenant_id`` against the bound tenant before any
session opens. The list-gold-sets query also filters
``tenant_id = :bound_tenant_id`` at the SQL layer as additional
defence-in-depth (per-tenant database routing is the primary
isolation per D32; the SQL predicate is the second layer).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel import TenantContext, TenantId

from contexts.retrieval_evaluation.adapters.outbound.postgres._tables import (
    gold_set_entries,
    gold_set_revisions,
    gold_sets,
)
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


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


class PostgresGoldSetReader:
    """Adapter implementation of ``GoldSetReader`` (D109)."""

    def __init__(
        self,
        *,
        per_tenant_sessionmaker_resolver: _SessionFactoryResolver,
        bound_tenant_id: TenantId,
    ) -> None:
        self._resolve_per_tenant = per_tenant_sessionmaker_resolver
        self._bound_tenant_id = bound_tenant_id

    def _assert_bound(self, tenant_context: TenantContext) -> None:
        if str(tenant_context.tenant_id) != str(self._bound_tenant_id):
            raise ValueError(
                f"TenantContext.tenant_id={tenant_context.tenant_id!r} does "
                f"not match adapter's bound tenant {self._bound_tenant_id!r}; "
                "tenant-isolation defence-in-depth per D24 / D32"
            )

    def _row_to_gold_set(self, row: sa.engine.Row) -> GoldSet:
        return GoldSet(
            id=UUID(row.id),
            tenant_id=UUID(row.tenant_id),
            jurisdiction=row.jurisdiction,
            name=row.name,
            created_by_user_id=row.created_by_user_id,
            created_at=row.created_at,
            current_revision_id=(
                UUID(row.current_revision_id)
                if row.current_revision_id
                else None
            ),
        )

    def _row_to_revision(self, row: sa.engine.Row) -> GoldSetRevision:
        return GoldSetRevision(
            id=UUID(row.id),
            gold_set_id=UUID(row.gold_set_id),
            revision_number=row.revision_number,
            status=GoldSetRevisionStatus(row.status),
            created_by_user_id=row.created_by_user_id,
            created_at=row.created_at,
            finalized_at=row.finalized_at,
            this_event_hash=row.this_event_hash,
            previous_event_hash=row.previous_event_hash,
        )

    def _row_to_entry(self, row: sa.engine.Row) -> GoldSetEntry:
        return GoldSetEntry(
            id=UUID(row.id),
            gold_set_revision_id=UUID(row.gold_set_revision_id),
            entry_index=row.entry_index,
            query=row.query,
            expected_chunk_ids=tuple(
                UUID(cid) for cid in row.expected_chunk_ids
            ),
        )

    async def list_gold_sets(
        self,
        *,
        tenant_context: TenantContext,
        cursor: GoldSetListCursor | None,
        page_size: int,
    ) -> GoldSetListPage:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            stmt = sa.select(gold_sets).where(
                gold_sets.c.tenant_id == str(self._bound_tenant_id)
            )
            if cursor is not None:
                stmt = stmt.where(
                    sa.tuple_(gold_sets.c.created_at, gold_sets.c.id)
                    < sa.tuple_(
                        sa.literal(cursor.created_at),
                        sa.literal(str(cursor.id)),
                    )
                )
            stmt = stmt.order_by(
                gold_sets.c.created_at.desc(), gold_sets.c.id.desc()
            ).limit(page_size + 1)
            rows = (await session.execute(stmt)).all()

        next_cursor: GoldSetListCursor | None = None
        if len(rows) > page_size:
            page_rows = rows[:page_size]
            last = page_rows[-1]
            next_cursor = GoldSetListCursor(
                created_at=last.created_at,
                id=UUID(last.id),
                page_size=page_size,
            )
        else:
            page_rows = rows
        return GoldSetListPage(
            gold_sets=tuple(self._row_to_gold_set(r) for r in page_rows),
            next_cursor=next_cursor,
        )

    async def get_gold_set_with_current_revision(
        self,
        *,
        tenant_context: TenantContext,
        gold_set_id: UUID,
    ) -> GoldSetWithCurrentRevision | None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            gs_row = (
                await session.execute(
                    sa.select(gold_sets).where(
                        sa.and_(
                            gold_sets.c.id == str(gold_set_id),
                            gold_sets.c.tenant_id
                            == str(self._bound_tenant_id),
                        )
                    )
                )
            ).one_or_none()
            if gs_row is None:
                return None
            gold_set = self._row_to_gold_set(gs_row)

            current_revision: GoldSetRevision | None = None
            entries: tuple[GoldSetEntry, ...] = ()
            if gold_set.current_revision_id is not None:
                rev_row = (
                    await session.execute(
                        sa.select(gold_set_revisions).where(
                            gold_set_revisions.c.id
                            == str(gold_set.current_revision_id)
                        )
                    )
                ).one_or_none()
                if rev_row is not None:
                    current_revision = self._row_to_revision(rev_row)
                    entry_rows = (
                        await session.execute(
                            sa.select(gold_set_entries)
                            .where(
                                gold_set_entries.c.gold_set_revision_id
                                == str(current_revision.id)
                            )
                            .order_by(gold_set_entries.c.entry_index.asc())
                        )
                    ).all()
                    entries = tuple(self._row_to_entry(r) for r in entry_rows)
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
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            joined = (
                await session.execute(
                    sa.select(gold_set_revisions, gold_sets.c.tenant_id)
                    .select_from(
                        gold_set_revisions.join(
                            gold_sets,
                            gold_set_revisions.c.gold_set_id == gold_sets.c.id,
                        )
                    )
                    .where(gold_set_revisions.c.id == str(revision_id))
                )
            ).one_or_none()
            if joined is None:
                return None
            if str(joined.tenant_id) != str(self._bound_tenant_id):
                return None
            revision = self._row_to_revision(joined)
            entry_rows = (
                await session.execute(
                    sa.select(gold_set_entries)
                    .where(
                        gold_set_entries.c.gold_set_revision_id
                        == str(revision_id)
                    )
                    .order_by(gold_set_entries.c.entry_index.asc())
                )
            ).all()
        return RevisionWithEntries(
            revision=revision,
            entries=tuple(self._row_to_entry(r) for r in entry_rows),
        )

    async def find_current_draft_revision(
        self,
        *,
        tenant_context: TenantContext,
        gold_set_id: UUID,
    ) -> GoldSetRevision | None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            gs_check = (
                await session.execute(
                    sa.select(gold_sets.c.id).where(
                        sa.and_(
                            gold_sets.c.id == str(gold_set_id),
                            gold_sets.c.tenant_id
                            == str(self._bound_tenant_id),
                        )
                    )
                )
            ).one_or_none()
            if gs_check is None:
                return None
            rev_row = (
                await session.execute(
                    sa.select(gold_set_revisions)
                    .where(
                        sa.and_(
                            gold_set_revisions.c.gold_set_id
                            == str(gold_set_id),
                            gold_set_revisions.c.status
                            == GoldSetRevisionStatus.DRAFT.value,
                        )
                    )
                    .order_by(gold_set_revisions.c.revision_number.desc())
                    .limit(1)
                )
            ).one_or_none()
        if rev_row is None:
            return None
        return self._row_to_revision(rev_row)
