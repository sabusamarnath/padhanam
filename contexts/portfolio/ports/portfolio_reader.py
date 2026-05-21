"""Read-side port for the portfolio context (D124).

Five methods: case get plus paginated list, data-point get plus
per-case list, and assertion history. DataPoints are returned with
their full revision history — the Revisable Protocol's
``revision_history`` surface requires it.

Tenant scoping flows through ``TenantContext``; cross-tenant reads
return ``None`` / empty per the tenant-isolation contract.

Ports layer is pure per D16 — no SQLAlchemy, no asyncpg.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from contexts.portfolio.domain import Assertion, Case, DataPoint
from contexts.portfolio.domain.query_filters import (
    CaseListCursor,
    CaseListFilters,
)
from shared_kernel import TenantContext


@dataclass(frozen=True)
class CaseListPage:
    """One page of ``list_cases`` output."""

    cases: tuple[Case, ...]
    next_cursor: CaseListCursor | None


class PortfolioReader(Protocol):
    """Read-side query port for the Case aggregate."""

    async def get_case(
        self, *, tenant_context: TenantContext, case_id: UUID
    ) -> Case | None:
        """Return the Case, or None when absent or cross-tenant."""
        ...

    async def list_cases(
        self,
        *,
        tenant_context: TenantContext,
        filters: CaseListFilters | None,
        cursor: CaseListCursor | None,
        page_size: int,
    ) -> CaseListPage:
        """List a tenant's cases, paginated on ``(created_at DESC, id DESC)``."""
        ...

    async def get_data_point(
        self, *, tenant_context: TenantContext, data_point_id: UUID
    ) -> DataPoint | None:
        """Return the DataPoint with its full revision history, or None."""
        ...

    async def list_data_points(
        self, *, tenant_context: TenantContext, case_id: UUID
    ) -> tuple[DataPoint, ...]:
        """List a case's DataPoints, each with its revision history."""
        ...

    async def assertion_history(
        self, *, tenant_context: TenantContext, data_point_id: UUID
    ) -> tuple[Assertion, ...]:
        """Return a DataPoint's assertions in chronological order."""
        ...


__all__ = ["CaseListPage", "PortfolioReader"]
