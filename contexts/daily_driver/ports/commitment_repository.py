"""Write/read port for the Commitment substrate (D157).

Tenant scoping flows through ``TenantContext``; cross-tenant reads
return empty / ``None`` per the tenant-isolation contract. Ports layer
is pure per D16 — no SQLAlchemy, no asyncpg.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from contexts.daily_driver.domain.commitment import (
    CheckinResponse,
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

    async def add_checkin_response(
        self,
        *,
        tenant_context: TenantContext,
        response: CheckinResponse,
    ) -> None:
        """Append one check-in response — the negative store (D192).

        Under the Option-B did-source, dids flow to the completion log; this
        records the ``reported_didnt`` negatives the cadence read consults.
        """
        ...

    async def completion_exists_on_day(
        self,
        *,
        tenant_context: TenantContext,
        commitment_id: UUID,
        day: date,
    ) -> bool:
        """True when a completion is logged for the commitment on ``day`` (UTC).

        The check-in write's completion-side idempotency guard (S97b); catches a
        prior check-in did and a Today "mark done" did alike."""
        ...

    async def checkin_response_exists_on_day(
        self,
        *,
        tenant_context: TenantContext,
        commitment_id: UUID,
        beat_date: date,
    ) -> bool:
        """True when a check-in response is recorded for the commitment on
        ``beat_date`` (S97b idempotency guard for the negative store)."""
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
