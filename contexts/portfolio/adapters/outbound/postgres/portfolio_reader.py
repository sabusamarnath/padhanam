"""Postgres adapter for PortfolioReader (D124, S43).

Implements ``PortfolioReader`` against per-tenant Postgres data
planes. SQLAlchemy 2.0 Core, manual row-to-entity materialisation,
no ORM, tenant-id bound at construction as defence-in-depth.

Cursor pagination on ``(created_at DESC, id DESC)`` with tuple
comparison; the cursor ``id`` literal is cast to ``pg.UUID``
explicitly per the S33 finding (uuid<varchar coercion broke
ordering). DataPoints are materialised with their full revision
history so the Revisable Protocol's ``revision_history`` holds.
"""

from __future__ import annotations

from typing import Protocol, Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel import ActorReference, TenantContext, TenantId

from contexts.portfolio.adapters.outbound.postgres._tables import (
    assertions as assertions_table,
)
from contexts.portfolio.adapters.outbound.postgres._tables import (
    cases as cases_table,
)
from contexts.portfolio.adapters.outbound.postgres._tables import (
    data_points as data_points_table,
)
from contexts.portfolio.domain import (
    Assertion,
    AssertionType,
    Case,
    CaseStatus,
    CaseType,
    DataPoint,
    DataPointType,
)
from contexts.portfolio.domain.query_filters import (
    CaseListCursor,
    CaseListFilters,
)
from contexts.portfolio.ports.portfolio_reader import CaseListPage


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


class PostgresPortfolioReader:
    """Adapter implementation of ``PortfolioReader`` (D124)."""

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

    @staticmethod
    def _row_to_case(row: sa.engine.Row) -> Case:
        return Case(
            id=UUID(row.id),
            tenant_id=UUID(row.tenant_id),
            jurisdiction=row.jurisdiction,
            title=row.title,
            case_type=CaseType(row.case_type),
            status=CaseStatus(row.status),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _row_to_assertion(row: sa.engine.Row) -> Assertion:
        return Assertion(
            id=UUID(row.id),
            data_point_id=UUID(row.data_point_id),
            tenant_id=UUID(row.tenant_id),
            jurisdiction=row.jurisdiction,
            assertion_type=AssertionType(row.assertion_type),
            revises_assertion_id=(
                UUID(row.revises_assertion_id)
                if row.revises_assertion_id is not None
                else None
            ),
            value=row.value,
            authored_by=ActorReference(user_id=row.authored_by_user_id),
            created_at=row.created_at,
        )

    @classmethod
    def _row_to_data_point(
        cls, row: sa.engine.Row, assertion_rows: Sequence[sa.engine.Row]
    ) -> DataPoint:
        return DataPoint(
            id=UUID(row.id),
            case_id=UUID(row.case_id),
            tenant_id=UUID(row.tenant_id),
            jurisdiction=row.jurisdiction,
            data_point_type=DataPointType(row.data_point_type),
            value=row.value,
            authored_by=ActorReference(user_id=row.authored_by_user_id),
            created_at=row.created_at,
            assertions=tuple(
                cls._row_to_assertion(a) for a in assertion_rows
            ),
            certainty=row.certainty,
        )

    async def _assertions_by_data_point(
        self, session: AsyncSession, data_point_ids: Sequence[str]
    ) -> dict[str, list[sa.engine.Row]]:
        if not data_point_ids:
            return {}
        rows = (
            await session.execute(
                sa.select(assertions_table)
                .where(
                    sa.and_(
                        assertions_table.c.data_point_id.in_(data_point_ids),
                        assertions_table.c.tenant_id
                        == str(self._bound_tenant_id),
                    )
                )
                .order_by(
                    assertions_table.c.data_point_id,
                    assertions_table.c.created_at,
                )
            )
        ).all()
        grouped: dict[str, list[sa.engine.Row]] = {}
        for row in rows:
            grouped.setdefault(row.data_point_id, []).append(row)
        return grouped

    async def get_case(
        self, *, tenant_context: TenantContext, case_id: UUID
    ) -> Case | None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            row = (
                await session.execute(
                    sa.select(cases_table).where(
                        sa.and_(
                            cases_table.c.id == str(case_id),
                            cases_table.c.tenant_id
                            == str(self._bound_tenant_id),
                        )
                    )
                )
            ).one_or_none()
        return None if row is None else self._row_to_case(row)

    async def list_cases(
        self,
        *,
        tenant_context: TenantContext,
        filters: CaseListFilters | None,
        cursor: CaseListCursor | None,
        page_size: int,
    ) -> CaseListPage:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            stmt = sa.select(cases_table).where(
                cases_table.c.tenant_id == str(self._bound_tenant_id)
            )
            if filters is not None and filters.case_types is not None:
                stmt = stmt.where(
                    cases_table.c.case_type.in_(
                        [ct.value for ct in filters.case_types]
                    )
                )
            if filters is not None and filters.statuses is not None:
                stmt = stmt.where(
                    cases_table.c.status.in_(
                        [s.value for s in filters.statuses]
                    )
                )
            if cursor is not None:
                stmt = stmt.where(
                    sa.tuple_(cases_table.c.created_at, cases_table.c.id)
                    < sa.tuple_(
                        sa.literal(cursor.created_at),
                        sa.cast(sa.literal(str(cursor.id)), pg.UUID),
                    )
                )
            stmt = stmt.order_by(
                cases_table.c.created_at.desc(), cases_table.c.id.desc()
            ).limit(page_size + 1)
            rows = (await session.execute(stmt)).all()

        next_cursor: CaseListCursor | None = None
        if len(rows) > page_size:
            page_rows = rows[:page_size]
            last = page_rows[-1]
            next_cursor = CaseListCursor(
                created_at=last.created_at,
                id=UUID(last.id),
                page_size=page_size,
            )
        else:
            page_rows = rows
        return CaseListPage(
            cases=tuple(self._row_to_case(r) for r in page_rows),
            next_cursor=next_cursor,
        )

    async def get_data_point(
        self, *, tenant_context: TenantContext, data_point_id: UUID
    ) -> DataPoint | None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            row = (
                await session.execute(
                    sa.select(data_points_table).where(
                        sa.and_(
                            data_points_table.c.id == str(data_point_id),
                            data_points_table.c.tenant_id
                            == str(self._bound_tenant_id),
                        )
                    )
                )
            ).one_or_none()
            if row is None:
                return None
            grouped = await self._assertions_by_data_point(session, [row.id])
        return self._row_to_data_point(row, grouped.get(row.id, []))

    async def list_data_points(
        self, *, tenant_context: TenantContext, case_id: UUID
    ) -> tuple[DataPoint, ...]:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            rows = (
                await session.execute(
                    sa.select(data_points_table)
                    .where(
                        sa.and_(
                            data_points_table.c.case_id == str(case_id),
                            data_points_table.c.tenant_id
                            == str(self._bound_tenant_id),
                        )
                    )
                    .order_by(data_points_table.c.created_at)
                )
            ).all()
            grouped = await self._assertions_by_data_point(
                session, [r.id for r in rows]
            )
        return tuple(
            self._row_to_data_point(r, grouped.get(r.id, [])) for r in rows
        )

    async def assertion_history(
        self, *, tenant_context: TenantContext, data_point_id: UUID
    ) -> tuple[Assertion, ...]:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            rows = (
                await session.execute(
                    sa.select(assertions_table)
                    .where(
                        sa.and_(
                            assertions_table.c.data_point_id
                            == str(data_point_id),
                            assertions_table.c.tenant_id
                            == str(self._bound_tenant_id),
                        )
                    )
                    .order_by(assertions_table.c.created_at)
                )
            ).all()
        return tuple(self._row_to_assertion(r) for r in rows)


__all__ = ["PostgresPortfolioReader"]
