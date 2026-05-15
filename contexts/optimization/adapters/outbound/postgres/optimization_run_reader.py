"""Postgres adapter for OptimizationRunReader (D111 cmt 2; S41).

Implements ``OptimizationRunReader`` against per-tenant Postgres
data planes. Mirrors ``PostgresEvaluationRunReader``: SQLAlchemy 2.0
Core, manual row-to-record materialisation, no ORM, tenant-id bound
at construction time as defence-in-depth.

Cursor pagination on ``(invoked_at DESC, id DESC)`` with tuple
comparison; the right-side ``id`` literal is cast to ``pg.UUID``
explicitly per the S33 finding (uuid<varchar coercion broke ordering).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel import TenantContext, TenantId

from contexts.optimization.adapters.outbound.postgres._tables import (
    optimization_runs,
)
from contexts.optimization.domain import (
    CategorySkipReason,
    OptimizationRun,
    OptimizationRunStatus,
)
from contexts.optimization.domain.query_filters import (
    OptimizationRunListCursor,
)
from contexts.optimization.ports.optimization_run_reader import (
    OptimizationRunListPage,
    OptimizationRunSnapshot,
)


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


class PostgresOptimizationRunReader:
    """Adapter implementation of ``OptimizationRunReader`` (D111)."""

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

    def _row_to_run(self, row: sa.engine.Row) -> OptimizationRun:
        skipped_raw = row.skipped_categories or {}
        skipped = {
            category: CategorySkipReason(
                reason_code=value["reason_code"],
                reason_text=value["reason_text"],
            )
            for category, value in skipped_raw.items()
        }
        return OptimizationRun(
            id=UUID(row.id),
            tenant_id=UUID(row.tenant_id),
            jurisdiction=row.jurisdiction,
            invoked_by_user_id=row.invoked_by_user_id,
            invoked_at=row.invoked_at,
            completed_at=row.completed_at,
            status=OptimizationRunStatus(row.status),
            skipped_categories=skipped,
        )

    async def get_optimization_run(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
    ) -> OptimizationRunSnapshot | None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            row = (
                await session.execute(
                    sa.select(optimization_runs).where(
                        sa.and_(
                            optimization_runs.c.id == str(run_id),
                            optimization_runs.c.tenant_id
                            == str(self._bound_tenant_id),
                        )
                    )
                )
            ).one_or_none()
        if row is None:
            return None
        return OptimizationRunSnapshot(run=self._row_to_run(row))

    async def list_optimization_runs(
        self,
        *,
        tenant_context: TenantContext,
        cursor: OptimizationRunListCursor | None,
        page_size: int,
    ) -> OptimizationRunListPage:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            stmt = sa.select(optimization_runs).where(
                optimization_runs.c.tenant_id == str(self._bound_tenant_id)
            )
            if cursor is not None:
                stmt = stmt.where(
                    sa.tuple_(
                        optimization_runs.c.invoked_at,
                        optimization_runs.c.id,
                    )
                    < sa.tuple_(
                        sa.literal(cursor.invoked_at),
                        sa.cast(sa.literal(str(cursor.id)), pg.UUID),
                    )
                )
            stmt = stmt.order_by(
                optimization_runs.c.invoked_at.desc(),
                optimization_runs.c.id.desc(),
            ).limit(page_size + 1)
            rows = (await session.execute(stmt)).all()

        next_cursor: OptimizationRunListCursor | None = None
        if len(rows) > page_size:
            page_rows = rows[:page_size]
            last = page_rows[-1]
            next_cursor = OptimizationRunListCursor(
                invoked_at=last.invoked_at,
                id=UUID(last.id),
                page_size=page_size,
            )
        else:
            page_rows = rows
        return OptimizationRunListPage(
            runs=tuple(self._row_to_run(r) for r in page_rows),
            next_cursor=next_cursor,
        )


__all__ = ["PostgresOptimizationRunReader"]
