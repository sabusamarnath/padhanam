"""Postgres adapter for MatcherQualityRunReader (D185, S90).

Implements the read port against per-tenant Postgres, mirroring
``PostgresEvaluationRunReader``: SQLAlchemy 2.0 Core, manual row-to-record
materialisation, no ORM, tenant-id bound at construction as defence-in-depth.
Orders by ``(computed_at DESC, id DESC)`` — newest measurement first.
"""

from __future__ import annotations

from typing import Protocol

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel import TenantContext, TenantId

from contexts.matcher_evaluation.adapters.outbound.postgres._tables import (
    matcher_quality_runs,
)
from contexts.matcher_evaluation.domain import (
    MatcherQualityMetrics,
    MatcherQualityRun,
)


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


def _row_to_run(row: sa.Row) -> MatcherQualityRun:
    from uuid import UUID

    return MatcherQualityRun(
        id=UUID(str(row.id)),
        tenant_id=UUID(str(row.tenant_id)),
        jurisdiction=row.jurisdiction,
        computed_at=row.computed_at,
        metrics=MatcherQualityMetrics(
            edge_count=row.edge_count,
            unit_count=row.unit_count,
            orphan_count=row.orphan_count,
            single_signal_count=row.single_signal_count,
            candidate_count=row.candidate_count,
            confirmed_count=row.confirmed_count,
        ),
    )


class PostgresMatcherQualityRunReader:
    """Adapter implementation of ``MatcherQualityRunReader`` (D185)."""

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

    async def get_latest_run(
        self, *, tenant_context: TenantContext
    ) -> MatcherQualityRun | None:
        runs = await self.list_runs(tenant_context=tenant_context, limit=1)
        return runs[0] if runs else None

    async def list_runs(
        self, *, tenant_context: TenantContext, limit: int
    ) -> tuple[MatcherQualityRun, ...]:
        self._assert_bound(tenant_context)
        t = matcher_quality_runs
        stmt = (
            sa.select(t)
            .where(t.c.tenant_id == str(self._bound_tenant_id))
            .order_by(t.c.computed_at.desc(), t.c.id.desc())
            .limit(limit)
        )
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            result = await session.execute(stmt)
            rows = result.fetchall()
        return tuple(_row_to_run(row) for row in rows)


__all__ = ["PostgresMatcherQualityRunReader"]
