"""Repository port for the PendingClarification aggregate (D134, S47).

The persistence-facing port the create / resolve / expire use cases
consume. Mirrors the ``MessageRepository`` shape: write plus read at
one port surface; tenant scoping flows through ``TenantContext``;
cross-tenant reads return ``None``.

``get_active_for_user`` returns the *single* PENDING for
``(tenant_id, user_id)`` if any — per the D134 invariant, at most
one PENDING exists per tuple at a time. The migration enforces the
invariant structurally via a partial unique index; the use case
respects it operationally by expiring any prior PENDING before
inserting a new one.

Ports layer is pure per D16 — no SQLAlchemy, no asyncpg.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from contexts.messaging.domain.pending_clarification import (
    PendingClarification,
)
from shared_kernel import TenantContext


class PendingClarificationRepository(Protocol):
    """Persistence-facing port for the PendingClarification aggregate."""

    async def save(
        self,
        *,
        tenant_context: TenantContext,
        pending: PendingClarification,
    ) -> None:
        """Persist a new PendingClarification (status=PENDING).

        Implementations rely on the migration's partial unique index
        on ``(tenant_id, user_id)`` WHERE ``status = 'PENDING'`` to
        enforce the at-most-one-PENDING invariant; the use case
        expires any prior PENDING before this call.
        """
        ...

    async def update_status(
        self,
        *,
        tenant_context: TenantContext,
        pending: PendingClarification,
    ) -> None:
        """Persist a lifecycle transition (PENDING → RESOLVED / EXPIRED)."""
        ...

    async def get_by_id(
        self,
        *,
        tenant_context: TenantContext,
        pending_id: UUID,
    ) -> PendingClarification | None:
        """Return the PendingClarification, or None when absent / cross-tenant."""
        ...

    async def get_active_for_user(
        self,
        *,
        tenant_context: TenantContext,
        user_id: str,
    ) -> PendingClarification | None:
        """Return the active PENDING for the (tenant, user), or None."""
        ...


__all__ = ["PendingClarificationRepository"]
