"""Postgres adapter for EvaluationRunReader (D110; S40 commit 4).

Implements ``EvaluationRunReader`` against per-tenant Postgres data
planes. Mirrors ``PostgresGoldSetReader`` at
``contexts/retrieval_evaluation/adapters/outbound/postgres/reader.py``:
SQLAlchemy 2.0 Core, manual row-to-record materialisation, no ORM,
tenant-id bound at construction time as defence-in-depth.

The list endpoint orders by ``(invoked_at DESC, id DESC)`` with a
tuple-comparison WHERE clause when a cursor is supplied; the S33
run_history precedent established this pattern at the platform.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
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
from contexts.retrieval_evaluation.domain.query_filters import (
    EvaluationRunListCursor,
)
from contexts.retrieval_evaluation.ports.evaluation_run_reader import (
    EvaluationRunListPage,
    EvaluationRunSnapshot,
)


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


class PostgresEvaluationRunReader:
    """Adapter implementation of ``EvaluationRunReader`` (D110)."""

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

    def _row_to_run(self, row: sa.engine.Row) -> EvaluationRun:
        return EvaluationRun(
            id=UUID(row.id),
            tenant_id=UUID(row.tenant_id),
            jurisdiction=row.jurisdiction,
            gold_set_id=UUID(row.gold_set_id),
            gold_set_revision_id=UUID(row.gold_set_revision_id),
            invoked_by_user_id=row.invoked_by_user_id,
            invoked_at=row.invoked_at,
            completed_at=row.completed_at,
            status=EvaluationRunStatus(row.status),
        )

    def _row_to_result(self, row: sa.engine.Row) -> EvaluationResult:
        return EvaluationResult(
            id=UUID(row.id),
            evaluation_run_id=UUID(row.evaluation_run_id),
            gold_set_entry_id=UUID(row.gold_set_entry_id),
            retrieval_strategy=row.retrieval_strategy,
            returned_chunk_ids=tuple(
                UUID(c) for c in row.returned_chunk_ids
            ),
            recall_at_k={int(k): float(v) for k, v in row.recall_at_k.items()},
            precision_at_k={
                int(k): float(v) for k, v in row.precision_at_k.items()
            },
            mrr=_decimal(row.mrr),
            latency_ms=int(row.latency_ms),
        )

    def _row_to_aggregate(self, row: sa.engine.Row) -> EvaluationAggregate:
        return EvaluationAggregate(
            id=UUID(row.id),
            evaluation_run_id=UUID(row.evaluation_run_id),
            retrieval_strategy=row.retrieval_strategy,
            recall_at_k_mean={
                int(k): float(v) for k, v in row.recall_at_k_mean.items()
            },
            precision_at_k_mean={
                int(k): float(v) for k, v in row.precision_at_k_mean.items()
            },
            mrr_mean=_decimal(row.mrr_mean),
            latency_ms_p50=int(row.latency_ms_p50),
            latency_ms_p95=int(row.latency_ms_p95),
            latency_ms_mean=int(row.latency_ms_mean),
        )

    async def list_runs(
        self,
        *,
        tenant_context: TenantContext,
        cursor: EvaluationRunListCursor | None,
        page_size: int,
    ) -> EvaluationRunListPage:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            stmt = sa.select(evaluation_runs).where(
                evaluation_runs.c.tenant_id == str(self._bound_tenant_id)
            )
            if cursor is not None:
                # Cast right-side literal to pg.UUID so the tuple-comparison
                # uses uuid<uuid semantics (cf. S33 finding at smoke time
                # where uuid<varchar fell back to a coercion that broke
                # ordering across pages).
                stmt = stmt.where(
                    sa.tuple_(
                        evaluation_runs.c.invoked_at,
                        evaluation_runs.c.id,
                    )
                    < sa.tuple_(
                        sa.literal(cursor.invoked_at),
                        sa.cast(sa.literal(str(cursor.id)), pg.UUID),
                    )
                )
            stmt = stmt.order_by(
                evaluation_runs.c.invoked_at.desc(),
                evaluation_runs.c.id.desc(),
            ).limit(page_size + 1)
            rows = (await session.execute(stmt)).all()

        next_cursor: EvaluationRunListCursor | None = None
        if len(rows) > page_size:
            page_rows = rows[:page_size]
            last = page_rows[-1]
            next_cursor = EvaluationRunListCursor(
                invoked_at=last.invoked_at,
                id=UUID(last.id),
                page_size=page_size,
            )
        else:
            page_rows = rows
        return EvaluationRunListPage(
            runs=tuple(self._row_to_run(r) for r in page_rows),
            next_cursor=next_cursor,
        )

    async def get_run_with_results_and_aggregates(
        self,
        *,
        tenant_context: TenantContext,
        run_id: UUID,
    ) -> EvaluationRunSnapshot | None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            run_row = (
                await session.execute(
                    sa.select(evaluation_runs).where(
                        sa.and_(
                            evaluation_runs.c.id == str(run_id),
                            evaluation_runs.c.tenant_id
                            == str(self._bound_tenant_id),
                        )
                    )
                )
            ).one_or_none()
            if run_row is None:
                return None
            run = self._row_to_run(run_row)
            result_rows = (
                await session.execute(
                    sa.select(evaluation_results)
                    .where(
                        evaluation_results.c.evaluation_run_id == str(run_id)
                    )
                    .order_by(
                        evaluation_results.c.gold_set_entry_id.asc(),
                        evaluation_results.c.retrieval_strategy.asc(),
                    )
                )
            ).all()
            aggregate_rows = (
                await session.execute(
                    sa.select(evaluation_aggregates)
                    .where(
                        evaluation_aggregates.c.evaluation_run_id
                        == str(run_id)
                    )
                    .order_by(evaluation_aggregates.c.retrieval_strategy.asc())
                )
            ).all()
        return EvaluationRunSnapshot(
            run=run,
            results=tuple(self._row_to_result(r) for r in result_rows),
            aggregates=tuple(
                self._row_to_aggregate(r) for r in aggregate_rows
            ),
        )


def _decimal(value: object) -> Decimal:
    """Stable Decimal coercion from a Postgres numeric column value."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


__all__ = ["PostgresEvaluationRunReader"]
