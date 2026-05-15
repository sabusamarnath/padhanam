"""Postgres adapter for RecommendationRepository (D111 cmt 3, 4; S41).

Implements ``RecommendationRepository`` against per-tenant Postgres
data planes. Two write methods:

- ``persist_recommendation`` inserts a row in ``generated`` state.
  The evidence_citations payload serializes via
  ``citations_to_payload`` from the domain layer.
- ``persist_status_transition`` updates the parent row's status,
  ``last_transition_at``, ``last_transition_by_user_id`` AND inserts
  the canonical transition row in one transaction; the WHERE clause
  on the UPDATE pins the prior status so concurrent transitions
  surface as ``rowcount=0`` and raise.

Bound-tenant-id defence-in-depth at construction.
"""

from __future__ import annotations

from typing import Protocol

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared_kernel import TenantContext, TenantId

from contexts.optimization.adapters.outbound.postgres._tables import (
    recommendation_status_transitions,
    recommendations,
)
from contexts.optimization.domain import (
    Recommendation,
    RecommendationStatusTransition,
)
from contexts.optimization.domain.citation_serialization import (
    citations_to_payload,
)


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


class PostgresRecommendationRepository:
    """Adapter implementation of ``RecommendationRepository`` (D111)."""

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

    async def persist_recommendation(
        self,
        *,
        tenant_context: TenantContext,
        recommendation: Recommendation,
    ) -> None:
        self._assert_bound(tenant_context)
        if str(recommendation.tenant_id) != str(self._bound_tenant_id):
            raise ValueError(
                f"Recommendation.tenant_id={recommendation.tenant_id!r} does "
                f"not match adapter's bound tenant "
                f"{self._bound_tenant_id!r}"
            )
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    sa.insert(recommendations).values(
                        id=str(recommendation.id),
                        tenant_id=str(recommendation.tenant_id),
                        jurisdiction=recommendation.jurisdiction,
                        category=recommendation.category.value,
                        subject=recommendation.subject,
                        text=recommendation.text,
                        evidence_citations=citations_to_payload(
                            recommendation.evidence_citations
                        ),
                        status=recommendation.status.value,
                        generated_at=recommendation.generated_at,
                        generated_by_run_id=str(
                            recommendation.generated_by_run_id
                        ),
                        last_transition_at=recommendation.last_transition_at,
                        last_transition_by_user_id=(
                            recommendation.last_transition_by_user_id
                        ),
                    )
                )

    async def persist_status_transition(
        self,
        *,
        tenant_context: TenantContext,
        updated_recommendation: Recommendation,
        transition: RecommendationStatusTransition,
    ) -> None:
        self._assert_bound(tenant_context)
        if (
            str(updated_recommendation.tenant_id)
            != str(self._bound_tenant_id)
        ):
            raise ValueError(
                f"Recommendation.tenant_id="
                f"{updated_recommendation.tenant_id!r} does not match "
                f"adapter's bound tenant {self._bound_tenant_id!r}"
            )
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                update_result = await session.execute(
                    sa.update(recommendations)
                    .where(
                        sa.and_(
                            recommendations.c.id
                            == str(updated_recommendation.id),
                            recommendations.c.tenant_id
                            == str(self._bound_tenant_id),
                            recommendations.c.status
                            == transition.from_status.value,
                        )
                    )
                    .values(
                        status=updated_recommendation.status.value,
                        last_transition_at=(
                            updated_recommendation.last_transition_at
                        ),
                        last_transition_by_user_id=(
                            updated_recommendation
                            .last_transition_by_user_id
                        ),
                    )
                )
                if update_result.rowcount != 1:
                    raise ValueError(
                        f"recommendation {updated_recommendation.id} is "
                        f"not in {transition.from_status.value!r} status "
                        f"or does not belong to bound tenant; cannot "
                        f"transition (rowcount={update_result.rowcount})"
                    )
                await session.execute(
                    sa.insert(recommendation_status_transitions).values(
                        id=str(transition.id),
                        recommendation_id=str(transition.recommendation_id),
                        from_status=transition.from_status.value,
                        to_status=transition.to_status.value,
                        transitioned_by_user_id=(
                            transition.transitioned_by_user_id
                        ),
                        transitioned_at=transition.transitioned_at,
                    )
                )


__all__ = ["PostgresRecommendationRepository"]
