"""Repository port for the intake context (D127).

A single port carries the intake aggregate's write and read
surfaces — ``save``, ``get_by_id``, ``list_for_tenant``. The
budget-table split trigger (a distinct reader port) does not fire
at S44b: the intake surface is small and the read and write shapes
share the IntakeRecord aggregate.

Tenant scoping flows through ``TenantContext``; cross-tenant reads
return ``None`` / empty per the tenant-isolation contract.

Ports layer is pure per D16 — no SQLAlchemy, no asyncpg.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from contexts.intake.domain import IntakeRecord
from contexts.intake.domain.query_filters import (
    IntakeListCursor,
    IntakeListFilters,
)
from shared_kernel import TenantContext


@dataclass(frozen=True)
class IntakeListPage:
    """One page of ``list_intakes`` output."""

    intakes: tuple[IntakeRecord, ...]
    next_cursor: IntakeListCursor | None


class IntakeRepository(Protocol):
    """Write-plus-read port for the IntakeRecord aggregate."""

    async def save(
        self, *, tenant_context: TenantContext, intake: IntakeRecord
    ) -> None:
        """Persist a new IntakeRecord. IntakeRecords are immutable."""
        ...

    async def get_by_id(
        self, *, tenant_context: TenantContext, intake_id: UUID
    ) -> IntakeRecord | None:
        """Return the IntakeRecord, or None when absent or cross-tenant."""
        ...

    async def list_for_tenant(
        self,
        *,
        tenant_context: TenantContext,
        filters: IntakeListFilters | None,
        cursor: IntakeListCursor | None,
        page_size: int,
    ) -> IntakeListPage:
        """List a tenant's intakes, paginated on ``(created_at DESC, id DESC)``."""
        ...


__all__ = ["IntakeListPage", "IntakeRepository"]
