"""Postgres adapter for EvaluationRunRepository (D137; S48b).

Mirrors the P11 retrieval-evaluation precedent at
``contexts/retrieval_evaluation/adapters/outbound/postgres/evaluation_run_repository.py``:
SQLAlchemy 2.0 Core, manual record-to-row conversion, no ORM.

Defence-in-depth tenant binding: the adapter is constructed with a
``bound_tenant_id``; every write validates the incoming
``TenantContext.tenant_id`` against the bound tenant before any
session opens. Per-tenant database routing is the primary isolation
per D32; the bound-tenant assertion is the second layer.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol
from uuid import uuid4

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
)
from shared_kernel import TenantContext, TenantId


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


class PostgresEvaluationRunRepository:
    """Adapter implementation of EvaluationRunRepository (D137)."""

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

    async def create_run(
        self, run: EvaluationRun, *, tenant: TenantContext
    ) -> None:
        self._assert_bound(tenant)
        if str(run.tenant_id) != str(self._bound_tenant_id):
            raise ValueError(
                f"EvaluationRun.tenant_id={run.tenant_id!r} does not match "
                f"adapter's bound tenant {self._bound_tenant_id!r}"
            )
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    sa.insert(intent_class_evaluation_runs).values(
                        id=str(run.id),
                        tenant_id=str(run.tenant_id),
                        jurisdiction=tenant.jurisdiction,
                        gold_set_name=run.gold_set_name,
                        model_provider=run.model_identifier.provider.value,
                        model_account=run.model_identifier.account,
                        model_version=run.model_identifier.version,
                        latency_tier=run.model_identifier.configuration.latency_tier.value,
                        invoked_by_user_id="operator",
                        started_at=run.started_at,
                        completed_at=run.completed_at,
                        status=run.status.value,
                        failure_reason=run.failure_reason,
                    )
                )

    async def update_run(
        self, run: EvaluationRun, *, tenant: TenantContext
    ) -> None:
        self._assert_bound(tenant)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    sa.update(intent_class_evaluation_runs)
                    .where(intent_class_evaluation_runs.c.id == str(run.id))
                    .values(
                        completed_at=run.completed_at,
                        status=run.status.value,
                        failure_reason=run.failure_reason,
                    )
                )

    async def append_result(
        self, result: EvaluationResult, *, tenant: TenantContext
    ) -> None:
        self._assert_bound(tenant)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    sa.insert(intent_class_evaluation_results).values(
                        id=str(uuid4()),
                        evaluation_run_id=str(result.run_id),
                        entry_index=result.entry_index,
                        input_phrasing=result.input_phrasing,
                        expected_intent_class=result.expected_intent_class,
                        classified_intent_class=result.classified_intent_class,
                        confidence=(
                            Decimal(str(round(result.confidence, 4)))
                            if result.confidence is not None
                            else None
                        ),
                        latency_ms=result.latency_ms,
                        parse_failure=result.parse_failure,
                        is_correct=result.is_correct,
                    )
                )

    async def write_aggregates(
        self,
        aggregates: tuple[EvaluationAggregate, ...],
        *,
        tenant: TenantContext,
    ) -> None:
        self._assert_bound(tenant)
        if not aggregates:
            return
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                for agg in aggregates:
                    await session.execute(
                        sa.insert(intent_class_evaluation_aggregates).values(
                            id=str(uuid4()),
                            evaluation_run_id=str(agg.run_id),
                            intent_class=agg.intent_class,
                            support=agg.support,
                            correct_count=agg.correct_count,
                            parse_failure_count=agg.parse_failure_count,
                            accuracy=Decimal(str(round(agg.accuracy, 4))),
                            recall=Decimal(str(round(agg.recall, 4))),
                            precision=Decimal(str(round(agg.precision, 4))),
                        )
                    )


__all__ = ["PostgresEvaluationRunRepository"]
