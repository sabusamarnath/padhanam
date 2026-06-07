"""GoalGraphPort — the daily-driver consumer port for the goal graph (D163).

The goal layer (Outcome nodes + lever-to-outcome edges) lives in the shared
graph, which the daily-driver context cannot reach directly: it may import
neither ``neo4j`` (the AST/``neo4j-confined`` fence) nor the ingestion context
(D17 independence). So daily_driver declares this consumer port and the apps
composition root bridges it to ingestion's ``OutcomeGraphPort`` — the
calendar/email ``MeetingGraphIndexPort`` + apps-bridge precedent.

The port speaks the daily-driver ``Goal`` domain (the bridge maps the generic
graph records onto it). Reads return goals with their lever + ladder; the raise
is the explicit, never-automatic target change (D9, the no-auto-modification
invariant). Ports layer is pure per D16 — no SQLAlchemy, no neo4j.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from contexts.daily_driver.domain.goal import Goal
from shared_kernel import TenantContext


class GoalGraphPort(Protocol):
    """Read/raise port for the goal layer in the shared graph (D163)."""

    async def list_goals(
        self, *, tenant_context: TenantContext
    ) -> tuple[Goal, ...]:
        """Return the tenant's goals, each with its lever + ladder."""
        ...

    async def raise_target_level(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
        commitment_id: UUID,
        new_target_level: str,
    ) -> str | None:
        """Set the goal's current target to ``new_target_level`` (the explicit
        raise). Returns the new level, or ``None`` when the goal is absent or
        cross-tenant. Never called automatically — only on an explicit action.
        """
        ...


__all__ = ["GoalGraphPort"]
