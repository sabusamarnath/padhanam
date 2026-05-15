"""Postgres adapter for GoldSetRepository (D109; S39 commit 5).

Implements ``GoldSetRepository`` against per-tenant Postgres data
planes per D32 / D34 / D36. SQLAlchemy 2.0 Core, manual record-to-row
conversion, no ORM. Mirrors the run_history-context writer shape at
``contexts/run_history/adapters/outbound/postgres/repository.py`` from
S31.

Defence-in-depth tenant binding: the adapter is constructed with a
``bound_tenant_id``; every write call validates the incoming
``TenantContext.tenant_id`` against the bound tenant before any
session opens. Mis-routed calls cannot land rows on the wrong
tenant's database.

``persist_new_gold_set`` and ``finalize_revision`` issue their two
writes inside a single ``async with session.begin()`` block so the
circular FK (gold_sets.current_revision_id → gold_set_revisions.id
and gold_set_revisions.gold_set_id → gold_sets.id) resolves cleanly
at commit time with the deferred constraint per D109's schema.
"""

from __future__ import annotations

from datetime import datetime
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


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


class PostgresGoldSetRepository:
    """Adapter implementation of ``GoldSetRepository`` (D109)."""

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

    async def persist_new_gold_set(
        self,
        *,
        tenant_context: TenantContext,
        gold_set: GoldSet,
        initial_revision: GoldSetRevision,
    ) -> None:
        self._assert_bound(tenant_context)
        if str(gold_set.tenant_id) != str(self._bound_tenant_id):
            raise ValueError(
                f"GoldSet.tenant_id={gold_set.tenant_id!r} does not match "
                f"adapter's bound tenant {self._bound_tenant_id!r}"
            )

        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    sa.insert(gold_sets).values(
                        id=str(gold_set.id),
                        tenant_id=str(gold_set.tenant_id),
                        jurisdiction=gold_set.jurisdiction,
                        name=gold_set.name,
                        created_by_user_id=gold_set.created_by_user_id,
                        created_at=gold_set.created_at,
                        current_revision_id=None,
                    )
                )
                await session.execute(
                    sa.insert(gold_set_revisions).values(
                        id=str(initial_revision.id),
                        gold_set_id=str(initial_revision.gold_set_id),
                        revision_number=initial_revision.revision_number,
                        status=initial_revision.status.value,
                        created_by_user_id=initial_revision.created_by_user_id,
                        created_at=initial_revision.created_at,
                        finalized_at=initial_revision.finalized_at,
                        this_event_hash=initial_revision.this_event_hash,
                        previous_event_hash=initial_revision.previous_event_hash,
                    )
                )

    async def open_new_draft_revision(
        self,
        *,
        tenant_context: TenantContext,
        revision: GoldSetRevision,
    ) -> None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    sa.insert(gold_set_revisions).values(
                        id=str(revision.id),
                        gold_set_id=str(revision.gold_set_id),
                        revision_number=revision.revision_number,
                        status=revision.status.value,
                        created_by_user_id=revision.created_by_user_id,
                        created_at=revision.created_at,
                        finalized_at=None,
                        this_event_hash=None,
                        previous_event_hash=None,
                    )
                )

    async def append_entry(
        self,
        *,
        tenant_context: TenantContext,
        entry: GoldSetEntry,
    ) -> None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                rev_status = (
                    await session.execute(
                        sa.select(gold_set_revisions.c.status).where(
                            gold_set_revisions.c.id
                            == str(entry.gold_set_revision_id)
                        )
                    )
                ).scalar_one_or_none()
                if rev_status != GoldSetRevisionStatus.DRAFT.value:
                    raise ValueError(
                        f"cannot append entry to revision "
                        f"{entry.gold_set_revision_id}: status is "
                        f"{rev_status!r}, expected 'draft'"
                    )
                await session.execute(
                    sa.insert(gold_set_entries).values(
                        id=str(entry.id),
                        gold_set_revision_id=str(entry.gold_set_revision_id),
                        entry_index=entry.entry_index,
                        query=entry.query,
                        expected_chunk_ids=[
                            str(cid) for cid in entry.expected_chunk_ids
                        ],
                    )
                )

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
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                update_result = await session.execute(
                    sa.update(gold_set_revisions)
                    .where(
                        sa.and_(
                            gold_set_revisions.c.id == str(revision_id),
                            gold_set_revisions.c.status
                            == GoldSetRevisionStatus.DRAFT.value,
                        )
                    )
                    .values(
                        status=GoldSetRevisionStatus.FINALIZED.value,
                        this_event_hash=this_event_hash,
                        previous_event_hash=previous_event_hash,
                        finalized_at=finalized_at,
                    )
                )
                if update_result.rowcount != 1:
                    raise ValueError(
                        f"revision {revision_id} is not in draft status; "
                        f"concurrent finalization or idempotent re-run "
                        f"detected (rowcount={update_result.rowcount})"
                    )
                await session.execute(
                    sa.update(gold_sets)
                    .where(gold_sets.c.id == str(gold_set_id))
                    .values(current_revision_id=str(revision_id))
                )
