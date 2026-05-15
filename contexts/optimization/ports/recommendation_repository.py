"""Write-side port for the Recommendation aggregate (D111 cmt 3, 4).

Two methods:

- ``persist_recommendation`` inserts a recommendation in ``generated``
  state at engine generation time. Atomic.
- ``persist_status_transition`` performs a status transition: updates
  the parent aggregate's status, ``last_transition_at``, and
  ``last_transition_by_user_id`` plus inserts the canonical
  ``recommendation_status_transitions`` row in a single transaction
  (the audit table is canonical for status-history drill-down;
  the parent's mirrored fields support read-time convenience without
  forcing a join on every read per D111 commitment 3).

Ports layer is pure per D16 — no SQLAlchemy, no asyncpg.
"""

from __future__ import annotations

from typing import Protocol

from contexts.optimization.domain import (
    Recommendation,
    RecommendationStatusTransition,
)
from shared_kernel.tenant_context import TenantContext


class RecommendationRepository(Protocol):
    """Write-side persistence for Recommendation."""

    async def persist_recommendation(
        self,
        *,
        tenant_context: TenantContext,
        recommendation: Recommendation,
    ) -> None:
        """Insert a recommendation row in ``generated`` state."""
        ...

    async def persist_status_transition(
        self,
        *,
        tenant_context: TenantContext,
        updated_recommendation: Recommendation,
        transition: RecommendationStatusTransition,
    ) -> None:
        """Persist a status transition atomically.

        Updates the recommendation row's ``status``,
        ``last_transition_at``, ``last_transition_by_user_id`` AND
        inserts the new transition row in one transaction. If either
        side fails the other rolls back.
        """
        ...


__all__ = ["RecommendationRepository"]
