"""get_recommendation read use case (D111 commitment 3)."""

from __future__ import annotations

from uuid import UUID

from contexts.optimization.domain import Recommendation
from contexts.optimization.ports.recommendation_reader import (
    RecommendationReader,
)
from shared_kernel.tenant_context import TenantContext


async def get_recommendation(
    *,
    tenant_context: TenantContext,
    recommendation_id: UUID,
    reader: RecommendationReader,
) -> Recommendation | None:
    """Return the recommendation aggregate or None.

    Cross-tenant access returns None per the tenant-isolation
    contract. The HTTP layer at S42 translates to 404.
    """
    return await reader.get_recommendation(
        tenant_context=tenant_context,
        recommendation_id=recommendation_id,
    )


__all__ = ["get_recommendation"]
