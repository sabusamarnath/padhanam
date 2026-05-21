"""Write-side port for the portfolio context (D124).

The Postgres adapter at
``contexts/portfolio/adapters/outbound/postgres/portfolio_repository.py``
implements this Protocol.

Tenant scoping flows through ``TenantContext``; the adapter is
constructed bound to a tenant and verifies the context plus the
entity's ``tenant_id`` as defence-in-depth per D24 / D32.

Ports layer is pure per D16 — no SQLAlchemy, no asyncpg.
"""

from __future__ import annotations

from typing import Protocol

from contexts.portfolio.domain import Assertion, Case, DataPoint
from shared_kernel import TenantContext


class PortfolioRepository(Protocol):
    """Write-side persistence for the Case aggregate."""

    async def save_case(
        self, *, tenant_context: TenantContext, case: Case
    ) -> None:
        """Insert a new ``cases`` row."""
        ...

    async def save_data_point(
        self, *, tenant_context: TenantContext, data_point: DataPoint
    ) -> None:
        """Insert a ``data_points`` row plus its assertions atomically.

        The data-point row and the assertion(s) carried on the entity
        at creation (the INITIAL assertion) land in one transaction.
        """
        ...

    async def save_assertion(
        self, *, tenant_context: TenantContext, assertion: Assertion
    ) -> None:
        """Append one ``assertions`` row — the revision-path write."""
        ...


__all__ = ["PortfolioRepository"]
