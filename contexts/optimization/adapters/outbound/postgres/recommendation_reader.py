"""Postgres adapter for RecommendationReader (D111 cmt 3, 4; S41).

Implements ``RecommendationReader`` against per-tenant Postgres data
planes. SQLAlchemy 2.0 Core, manual row-to-record materialisation,
no ORM, tenant-id bound at construction time.

Filter dimensions (category, status) translate to IN-clause WHERE
filters when present. Cursor pagination on ``(generated_at DESC, id
DESC)`` with tuple comparison; the right-side ``id`` literal is cast
to ``pg.UUID`` per the S33 finding.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel import TenantContext, TenantId

from contexts.optimization.adapters.outbound.postgres._tables import (
    recommendations,
)
from contexts.optimization.domain import (
    Recommendation,
    RecommendationCategory,
    RecommendationStatus,
)
from contexts.optimization.domain.citation_serialization import (
    citations_from_payload,
)
from contexts.optimization.domain.query_filters import (
    RecommendationListCursor,
    RecommendationListFilters,
)
from contexts.optimization.ports.recommendation_reader import (
    RecommendationListPage,
)


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


class PostgresRecommendationReader:
    """Adapter implementation of ``RecommendationReader`` (D111)."""

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

    def _row_to_recommendation(self, row: sa.engine.Row) -> Recommendation:
        return Recommendation(
            id=UUID(row.id),
            tenant_id=UUID(row.tenant_id),
            jurisdiction=row.jurisdiction,
            category=RecommendationCategory(row.category),
            subject=row.subject,
            text=row.text,
            evidence_citations=citations_from_payload(row.evidence_citations),
            status=RecommendationStatus(row.status),
            generated_at=row.generated_at,
            generated_by_run_id=UUID(row.generated_by_run_id),
            last_transition_at=row.last_transition_at,
            last_transition_by_user_id=row.last_transition_by_user_id,
        )

    async def get_recommendation(
        self,
        *,
        tenant_context: TenantContext,
        recommendation_id: UUID,
    ) -> Recommendation | None:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            row = (
                await session.execute(
                    sa.select(recommendations).where(
                        sa.and_(
                            recommendations.c.id == str(recommendation_id),
                            recommendations.c.tenant_id
                            == str(self._bound_tenant_id),
                        )
                    )
                )
            ).one_or_none()
        if row is None:
            return None
        return self._row_to_recommendation(row)

    async def list_recommendations(
        self,
        *,
        tenant_context: TenantContext,
        filters: RecommendationListFilters,
        cursor: RecommendationListCursor | None,
        page_size: int,
    ) -> RecommendationListPage:
        self._assert_bound(tenant_context)
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            stmt = sa.select(recommendations).where(
                recommendations.c.tenant_id == str(self._bound_tenant_id)
            )
            if filters.categories is not None:
                stmt = stmt.where(
                    recommendations.c.category.in_(
                        tuple(c.value for c in filters.categories)
                    )
                )
            if filters.statuses is not None:
                stmt = stmt.where(
                    recommendations.c.status.in_(
                        tuple(s.value for s in filters.statuses)
                    )
                )
            if cursor is not None:
                stmt = stmt.where(
                    sa.tuple_(
                        recommendations.c.generated_at,
                        recommendations.c.id,
                    )
                    < sa.tuple_(
                        sa.literal(cursor.generated_at),
                        sa.cast(sa.literal(str(cursor.id)), pg.UUID),
                    )
                )
            stmt = stmt.order_by(
                recommendations.c.generated_at.desc(),
                recommendations.c.id.desc(),
            ).limit(page_size + 1)
            rows = (await session.execute(stmt)).all()

        next_cursor: RecommendationListCursor | None = None
        if len(rows) > page_size:
            page_rows = rows[:page_size]
            last = page_rows[-1]
            next_cursor = RecommendationListCursor(
                generated_at=last.generated_at,
                id=UUID(last.id),
                page_size=page_size,
            )
        else:
            page_rows = rows
        return RecommendationListPage(
            recommendations=tuple(
                self._row_to_recommendation(r) for r in page_rows
            ),
            next_cursor=next_cursor,
        )


__all__ = ["PostgresRecommendationReader"]
