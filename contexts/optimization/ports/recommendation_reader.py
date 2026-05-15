"""Read-side port for Recommendation queries (D111 cmt 3, 4).

Two methods:

- ``get_recommendation`` returns the recommendation aggregate
  including its discriminated evidence-citations payload.
- ``list_recommendations`` returns a paginated page filtered by
  category and status (multi-value match per
  ``RecommendationListFilters``).

Tenant scoping flows through ``TenantContext``; cross-tenant reads
return ``None`` / empty pages per the tenant-isolation contract.

Ports layer is pure per D16 — no SQLAlchemy, no asyncpg.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from contexts.optimization.domain import Recommendation
from contexts.optimization.domain.query_filters import (
    RecommendationListCursor,
    RecommendationListFilters,
)
from shared_kernel.tenant_context import TenantContext


@dataclass(frozen=True)
class RecommendationListPage:
    """One page of ``list_recommendations`` output."""

    recommendations: tuple[Recommendation, ...]
    next_cursor: RecommendationListCursor | None


class RecommendationReader(Protocol):
    """Read-side query port for Recommendation."""

    async def get_recommendation(
        self,
        *,
        tenant_context: TenantContext,
        recommendation_id: UUID,
    ) -> Recommendation | None:
        """Return the recommendation aggregate or None.

        Returns None when the recommendation does not exist or
        belongs to a different tenant (tenant_isolation contract).
        """
        ...

    async def list_recommendations(
        self,
        *,
        tenant_context: TenantContext,
        filters: RecommendationListFilters,
        cursor: RecommendationListCursor | None,
        page_size: int,
    ) -> RecommendationListPage:
        """List recommendations, paginated and filtered.

        Sort order is fixed at ``generated_at DESC, id DESC``.
        Filter dimensions are multi-value; empty filters return the
        full page.
        """
        ...


__all__ = [
    "RecommendationListPage",
    "RecommendationReader",
]
