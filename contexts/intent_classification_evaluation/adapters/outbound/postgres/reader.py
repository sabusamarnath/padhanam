"""Postgres adapter for EvaluationRunReader (D137; S48b).

Read-side adapter complementing the repository adapter. Same
defence-in-depth tenant binding pattern.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.intent_classification_evaluation.adapters.outbound.postgres._tables import (
    intent_class_evaluation_aggregates,
    intent_class_evaluation_results,
    intent_class_evaluation_runs,
)
from contexts.intent_classification_evaluation.domain.evaluation_result import (
    EvaluationAggregate,
    EvaluationResult,
)
from contexts.intent_classification_evaluation.domain.evaluation_run import (
    EvaluationRun,
    EvaluationRunStatus,
)
from shared_kernel import TenantContext, TenantId
from shared_kernel.inference import (
    DEFAULT_ACCOUNT,
    LatencyTier,
    ModelConfiguration,
    ModelIdentifier,
    Provider,
)


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


def _row_to_run(row: sa.Row) -> EvaluationRun:
    """Reconstruct an EvaluationRun aggregate from a row."""
    return EvaluationRun(
        id=UUID(str(row.id)),
        tenant_id=UUID(str(row.tenant_id)),
        gold_set_name=row.gold_set_name,
        model_identifier=ModelIdentifier(
            provider=Provider(row.model_provider),
            account=row.model_account or DEFAULT_ACCOUNT,
            version=row.model_version,
            configuration=ModelConfiguration(
                latency_tier=LatencyTier(row.latency_tier),
                temperature=0.0,
                max_tokens=None,
                structured_output_schema=None,
            ),
        ),
        status=EvaluationRunStatus(row.status),
        started_at=row.started_at,
        completed_at=row.completed_at,
        failure_reason=row.failure_reason,
    )


def _row_to_result(row: sa.Row) -> EvaluationResult:
    return EvaluationResult(
        run_id=UUID(str(row.evaluation_run_id)),
        entry_index=row.entry_index,
        input_phrasing=row.input_phrasing,
        expected_intent_class=row.expected_intent_class,
        classified_intent_class=row.classified_intent_class,
        confidence=(
            float(row.confidence) if row.confidence is not None else None
        ),
        latency_ms=row.latency_ms,
        parse_failure=row.parse_failure,
        is_correct=row.is_correct,
    )


def _row_to_aggregate(row: sa.Row) -> EvaluationAggregate:
    return EvaluationAggregate(
        run_id=UUID(str(row.evaluation_run_id)),
        intent_class=row.intent_class,
        support=row.support,
        correct_count=row.correct_count,
        parse_failure_count=row.parse_failure_count,
        accuracy=float(row.accuracy),
        recall=float(row.recall),
        precision=float(row.precision),
    )


class PostgresEvaluationRunReader:
    """Adapter implementation of EvaluationRunReader (D137)."""

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
                f"not match adapter's bound tenant {self._bound_tenant_id!r}"
            )

    async def get_run(
        self, run_id: UUID, *, tenant: TenantContext
    ) -> EvaluationRun | None:
        self._assert_bound(tenant)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            result = await session.execute(
                sa.select(intent_class_evaluation_runs).where(
                    intent_class_evaluation_runs.c.id == str(run_id)
                )
            )
            row = result.first()
            return _row_to_run(row) if row is not None else None

    async def list_runs(
        self, *, tenant: TenantContext, limit: int = 20
    ) -> tuple[EvaluationRun, ...]:
        self._assert_bound(tenant)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            result = await session.execute(
                sa.select(intent_class_evaluation_runs)
                .order_by(intent_class_evaluation_runs.c.started_at.desc())
                .limit(limit)
            )
            return tuple(_row_to_run(r) for r in result.fetchall())

    async def list_results(
        self, run_id: UUID, *, tenant: TenantContext
    ) -> tuple[EvaluationResult, ...]:
        self._assert_bound(tenant)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            result = await session.execute(
                sa.select(intent_class_evaluation_results)
                .where(
                    intent_class_evaluation_results.c.evaluation_run_id
                    == str(run_id)
                )
                .order_by(intent_class_evaluation_results.c.entry_index)
            )
            return tuple(_row_to_result(r) for r in result.fetchall())

    async def list_aggregates(
        self, run_id: UUID, *, tenant: TenantContext
    ) -> tuple[EvaluationAggregate, ...]:
        self._assert_bound(tenant)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            result = await session.execute(
                sa.select(intent_class_evaluation_aggregates).where(
                    intent_class_evaluation_aggregates.c.evaluation_run_id
                    == str(run_id)
                )
            )
            return tuple(_row_to_aggregate(r) for r in result.fetchall())


__all__ = ["PostgresEvaluationRunReader"]
