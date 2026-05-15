"""Postgres adapter for EvaluationRunRepository (D110; S40 commit 4).

Implements ``EvaluationRunRepository`` against per-tenant Postgres
data planes per D32 / D34 / D36. Mirrors ``PostgresGoldSetRepository``
at ``contexts/retrieval_evaluation/adapters/outbound/postgres/repository.py``:
SQLAlchemy 2.0 Core, manual record-to-row conversion, no ORM.

Defence-in-depth tenant binding: the adapter is constructed with a
``bound_tenant_id``; every write call validates the incoming
``TenantContext.tenant_id`` against the bound tenant before any
session opens. Per-tenant database routing is the primary isolation
per D32; the bound-tenant assertion is the second layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel import TenantContext, TenantId

from contexts.retrieval_evaluation.adapters.outbound.postgres._tables import (
    evaluation_aggregates,
    evaluation_results,
    evaluation_runs,
)
from contexts.retrieval_evaluation.domain import (
    EvaluationAggregate,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunStatus,
)


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


class PostgresEvaluationRunRepository:
    """Adapter implementation of ``EvaluationRunRepository`` (D110)."""

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
        run: EvaluationRun,
    ) -> None:
        self._assert_bound(tenant_context)
        if str(run.tenant_id) != str(self._bound_tenant_id):
            raise ValueError(
                f"EvaluationRun.tenant_id={run.tenant_id!r} does not match "
                f"adapter's bound tenant {self._bound_tenant_id!r}"
            )
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    sa.insert(evaluation_runs).values(
                        id=str(run.id),
                        tenant_id=str(run.tenant_id),
                        jurisdiction=run.jurisdiction,
                        gold_set_id=str(run.gold_set_id),
                        gold_set_revision_id=str(run.gold_set_revision_id),
                        invoked_by_user_id=run.invoked_by_user_id,
                        invoked_at=run.invoked_at,
                        completed_at=run.completed_at,
                        status=run.status.value,
                    )
                )

    async def persist_result(
        self,
        *,
        tenant_context: TenantContext,
        result: EvaluationResult,
    ) -> None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    sa.insert(evaluation_results).values(
                        id=str(result.id),
                        evaluation_run_id=str(result.evaluation_run_id),
                        gold_set_entry_id=str(result.gold_set_entry_id),
                        retrieval_strategy=result.retrieval_strategy,
                        returned_chunk_ids=[
                            str(c) for c in result.returned_chunk_ids
                        ],
                        recall_at_k={
                            str(k): v for k, v in result.recall_at_k.items()
                        },
                        precision_at_k={
                            str(k): v for k, v in result.precision_at_k.items()
                        },
                        mrr=result.mrr,
                        latency_ms=result.latency_ms,
                    )
                )

    async def persist_aggregate(
        self,
        *,
        tenant_context: TenantContext,
        aggregate: EvaluationAggregate,
    ) -> None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    sa.insert(evaluation_aggregates).values(
                        id=str(aggregate.id),
                        evaluation_run_id=str(aggregate.evaluation_run_id),
                        retrieval_strategy=aggregate.retrieval_strategy,
                        recall_at_k_mean={
                            str(k): v
                            for k, v in aggregate.recall_at_k_mean.items()
                        },
                        precision_at_k_mean={
                            str(k): v
                            for k, v in aggregate.precision_at_k_mean.items()
                        },
                        mrr_mean=aggregate.mrr_mean,
                        latency_ms_p50=aggregate.latency_ms_p50,
                        latency_ms_p95=aggregate.latency_ms_p95,
                        latency_ms_mean=aggregate.latency_ms_mean,
                    )
                )

    async def mark_completed(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
        completed_at: datetime,
    ) -> None:
        await self._transition_to_terminal(
            tenant_context=tenant_context,
            run_id=run_id,
            completed_at=completed_at,
            new_status=EvaluationRunStatus.COMPLETED,
        )

    async def mark_failed(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
        completed_at: datetime,
    ) -> None:
        await self._transition_to_terminal(
            tenant_context=tenant_context,
            run_id=run_id,
            completed_at=completed_at,
            new_status=EvaluationRunStatus.FAILED,
        )

    async def _transition_to_terminal(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
        completed_at: datetime,
        new_status: EvaluationRunStatus,
    ) -> None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                # WHERE clause pins the prior status to 'running' so concurrent
                # transitions and idempotent re-runs surface as rowcount=0.
                update_result = await session.execute(
                    sa.update(evaluation_runs)
                    .where(
                        sa.and_(
                            evaluation_runs.c.id == str(run_id),
                            evaluation_runs.c.tenant_id
                            == str(self._bound_tenant_id),
                            evaluation_runs.c.status
                            == EvaluationRunStatus.RUNNING.value,
                        )
                    )
                    .values(
                        status=new_status.value,
                        completed_at=completed_at,
                    )
                )
                if update_result.rowcount != 1:
                    raise ValueError(
                        f"evaluation run {run_id} is not in 'running' status "
                        f"or does not belong to bound tenant; cannot transition "
                        f"to {new_status.value} (rowcount="
                        f"{update_result.rowcount})"
                    )


__all__ = ["PostgresEvaluationRunRepository"]
