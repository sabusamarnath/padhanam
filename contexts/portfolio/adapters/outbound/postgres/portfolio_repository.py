"""Postgres adapter for PortfolioRepository (D124, S43).

Implements ``PortfolioRepository`` against per-tenant Postgres data
planes per D32 / D34 / D36. Mirrors the optimization-context adapter
shape: SQLAlchemy 2.0 Core, manual entity-to-row conversion, no ORM,
bound-tenant-id defence-in-depth at construction.
"""

from __future__ import annotations

from typing import Any, Protocol

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel import TenantContext, TenantId

from contexts.portfolio.adapters.outbound.postgres._tables import (
    assertions as assertions_table,
)
from contexts.portfolio.adapters.outbound.postgres._tables import (
    cases as cases_table,
)
from contexts.portfolio.adapters.outbound.postgres._tables import (
    data_points as data_points_table,
)
from contexts.portfolio.domain import Assertion, Case, DataPoint


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


def _assertion_row(assertion: Assertion) -> dict[str, Any]:
    return {
        "id": str(assertion.id),
        "data_point_id": str(assertion.data_point_id),
        "tenant_id": str(assertion.tenant_id),
        "jurisdiction": assertion.jurisdiction,
        "assertion_type": assertion.assertion_type.value,
        "revises_assertion_id": (
            str(assertion.revises_assertion_id)
            if assertion.revises_assertion_id is not None
            else None
        ),
        "value": assertion.value,
        "authored_by_user_id": assertion.authored_by.user_id,
        "created_at": assertion.created_at,
        "intake_id": (
            str(assertion.intake_id)
            if assertion.intake_id is not None
            else None
        ),
    }


class PostgresPortfolioRepository:
    """Adapter implementation of ``PortfolioRepository`` (D124)."""

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

    def _assert_entity_tenant(self, entity_tenant_id: object, label: str) -> None:
        if str(entity_tenant_id) != str(self._bound_tenant_id):
            raise ValueError(
                f"{label}.tenant_id={entity_tenant_id!r} does not match "
                f"adapter's bound tenant {self._bound_tenant_id!r}"
            )

    async def save_case(
        self, *, tenant_context: TenantContext, case: Case
    ) -> None:
        self._assert_bound(tenant_context)
        self._assert_entity_tenant(case.tenant_id, "Case")
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    sa.insert(cases_table).values(
                        id=str(case.id),
                        tenant_id=str(case.tenant_id),
                        jurisdiction=case.jurisdiction,
                        title=case.title,
                        case_type=case.case_type.value,
                        status=case.status.value,
                        created_at=case.created_at,
                        updated_at=case.updated_at,
                        intake_id=(
                            str(case.intake_id)
                            if case.intake_id is not None
                            else None
                        ),
                    )
                )

    async def save_data_point(
        self, *, tenant_context: TenantContext, data_point: DataPoint
    ) -> None:
        self._assert_bound(tenant_context)
        self._assert_entity_tenant(data_point.tenant_id, "DataPoint")
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    sa.insert(data_points_table).values(
                        id=str(data_point.id),
                        case_id=str(data_point.case_id),
                        tenant_id=str(data_point.tenant_id),
                        jurisdiction=data_point.jurisdiction,
                        data_point_type=data_point.data_point_type.value,
                        value=data_point.value,
                        authored_by_user_id=data_point.authored_by.user_id,
                        certainty=data_point.certainty,
                        created_at=data_point.created_at,
                    )
                )
                for assertion in data_point.assertions:
                    await session.execute(
                        sa.insert(assertions_table).values(
                            **_assertion_row(assertion)
                        )
                    )

    async def save_assertion(
        self, *, tenant_context: TenantContext, assertion: Assertion
    ) -> None:
        self._assert_bound(tenant_context)
        self._assert_entity_tenant(assertion.tenant_id, "Assertion")
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    sa.insert(assertions_table).values(
                        **_assertion_row(assertion)
                    )
                )


__all__ = ["PostgresPortfolioRepository"]
