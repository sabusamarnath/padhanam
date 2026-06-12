"""Postgres adapter for MatcherQualityRunRepository (D185, S90).

Implements the write port against per-tenant Postgres data planes (D32/D34/D36),
mirroring ``PostgresEvaluationRunRepository``: SQLAlchemy 2.0 Core, manual
record-to-row conversion, no ORM, tenant-id bound at construction time as
defence-in-depth.
"""

from __future__ import annotations

from typing import Protocol

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel import TenantContext, TenantId

from contexts.matcher_evaluation.adapters.outbound.postgres._tables import (
    matcher_quality_runs,
)
from contexts.matcher_evaluation.domain import MatcherQualityRun


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


class PostgresMatcherQualityRunRepository:
    """Adapter implementation of ``MatcherQualityRunRepository`` (D185)."""

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

    async def save(
        self, *, tenant_context: TenantContext, run: MatcherQualityRun
    ) -> None:
        self._assert_bound(tenant_context)
        if str(run.tenant_id) != str(self._bound_tenant_id):
            raise ValueError(
                f"MatcherQualityRun.tenant_id={run.tenant_id!r} does not match "
                f"adapter's bound tenant {self._bound_tenant_id!r}"
            )
        m = run.metrics
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    sa.insert(matcher_quality_runs).values(
                        id=str(run.id),
                        tenant_id=str(run.tenant_id),
                        jurisdiction=run.jurisdiction,
                        computed_at=run.computed_at,
                        edge_count=m.edge_count,
                        unit_count=m.unit_count,
                        orphan_count=m.orphan_count,
                        single_signal_count=m.single_signal_count,
                        candidate_count=m.candidate_count,
                        confirmed_count=m.confirmed_count,
                        single_signal_share=m.single_signal_share,
                        candidate_to_confirmed_ratio=m.candidate_to_confirmed_ratio,
                        orphan_rate=m.orphan_rate,
                    )
                )


__all__ = ["PostgresMatcherQualityRunRepository"]
