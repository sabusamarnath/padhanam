"""Write/read port for the Commitment substrate (D157).

Tenant scoping flows through ``TenantContext``; cross-tenant reads
return empty / ``None`` per the tenant-isolation contract. Ports layer
is pure per D16 — no SQLAlchemy, no asyncpg.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from contexts.daily_driver.domain.commitment import (
    Commitment,
    CommitmentActivity,
    CommitmentCompletion,
    OutcomeStatus,
)
from shared_kernel import TenantContext


class CommitmentRepository(Protocol):
    """Persistence port for Commitments and their completion log."""

    async def add_commitment(
        self, *, tenant_context: TenantContext, commitment: Commitment
    ) -> None:
        """Persist a new Commitment."""
        ...

    async def add_completion(
        self,
        *,
        tenant_context: TenantContext,
        completion: CommitmentCompletion,
    ) -> None:
        """Append one entry to a Commitment's completion log."""
        ...

    async def get_commitment(
        self, *, tenant_context: TenantContext, commitment_id: UUID
    ) -> Commitment | None:
        """Return the Commitment, or None when absent or cross-tenant."""
        ...

    async def record_observed_outcome(
        self,
        *,
        tenant_context: TenantContext,
        commitment_id: UUID,
        observed_outcome: str | None,
        outcome_status: OutcomeStatus,
        observed_at: datetime,
    ) -> Commitment | None:
        """Set the observed outcome + status on a Commitment (D162).

        Returns the updated Commitment, or None when absent or
        cross-tenant. ``observed_at`` is the new progress signal.
        """
        ...

    async def list_with_activity(
        self, *, tenant_context: TenantContext
    ) -> tuple[CommitmentActivity, ...]:
        """List the tenant's Commitments, each with its last completion time."""
        ...


__all__ = ["CommitmentRepository"]
