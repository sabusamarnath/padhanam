"""Postgres adapter for OptimizationRunRepository (D111 cmt 2; S41).

Implements ``OptimizationRunRepository`` against per-tenant Postgres
data planes per D32 / D34 / D36. Mirrors
``PostgresEvaluationRunRepository`` shape: SQLAlchemy 2.0 Core,
manual record-to-row conversion, no ORM, bound-tenant-id defence-in-
depth at construction.

Status-transition writes pin the prior status to ``running`` in the
WHERE clause; concurrent transitions or idempotent re-runs surface
as ``rowcount=0`` and raise.
"""

from __future__ import annotations

from datetime import datetime
from typing import Mapping, Protocol
from uuid import UUID

import sqlalchemy as sa
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
from contexts.optimization.domain.citation_serialization import (
    skipped_categories_to_dict,
)


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


class PostgresOptimizationRunRepository:
    """Adapter implementation of ``OptimizationRunRepository`` (D111)."""

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

    async def persist_run(
        self,
        *,
        tenant_context: TenantContext,
        run: OptimizationRun,
    ) -> None:
        self._assert_bound(tenant_context)
        if str(run.tenant_id) != str(self._bound_tenant_id):
            raise ValueError(
                f"OptimizationRun.tenant_id={run.tenant_id!r} does not match "
                f"adapter's bound tenant {self._bound_tenant_id!r}"
            )
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    sa.insert(optimization_runs).values(
                        id=str(run.id),
                        tenant_id=str(run.tenant_id),
                        jurisdiction=run.jurisdiction,
                        invoked_by_user_id=run.invoked_by_user_id,
                        invoked_at=run.invoked_at,
                        completed_at=run.completed_at,
                        status=run.status.value,
                        skipped_categories=skipped_categories_to_dict(
                            run.skipped_categories
                        ),
                    )
                )

    async def mark_completed(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
        completed_at: datetime,
        skipped_categories: Mapping[str, CategorySkipReason],
    ) -> None:
        await self._transition_to_terminal(
            tenant_context=tenant_context,
            run_id=run_id,
            completed_at=completed_at,
            new_status=OptimizationRunStatus.COMPLETED,
            skipped_categories=skipped_categories,
        )

    async def mark_failed(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
        completed_at: datetime,
    ) -> None:
        # Preserve any skip-reasons accumulated before failure; the
        # caller is responsible for passing them via mark_completed if
        # they want them persisted. mark_failed leaves the JSONB column
        # as written at persist_run time.
        await self._transition_to_terminal(
            tenant_context=tenant_context,
            run_id=run_id,
            completed_at=completed_at,
            new_status=OptimizationRunStatus.FAILED,
            skipped_categories=None,
        )

    async def _transition_to_terminal(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
        completed_at: datetime,
        new_status: OptimizationRunStatus,
        skipped_categories: Mapping[str, CategorySkipReason] | None,
    ) -> None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        values: dict[str, object] = {
            "status": new_status.value,
            "completed_at": completed_at,
        }
        if skipped_categories is not None:
            values["skipped_categories"] = skipped_categories_to_dict(
                skipped_categories
            )
        async with sessionmaker() as session:
            async with session.begin():
                update_result = await session.execute(
                    sa.update(optimization_runs)
                    .where(
                        sa.and_(
                            optimization_runs.c.id == str(run_id),
                            optimization_runs.c.tenant_id
                            == str(self._bound_tenant_id),
                            optimization_runs.c.status
                            == OptimizationRunStatus.RUNNING.value,
                        )
                    )
                    .values(**values)
                )
                if update_result.rowcount != 1:
                    raise ValueError(
                        f"optimization run {run_id} is not in 'running' "
                        f"status or does not belong to bound tenant; cannot "
                        f"transition to {new_status.value} (rowcount="
                        f"{update_result.rowcount})"
                    )


__all__ = ["PostgresOptimizationRunRepository"]
