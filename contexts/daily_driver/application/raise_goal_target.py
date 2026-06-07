"""raise_goal_target use case — the explicit target raise (S62, D163).

The raise is recommendation-shaped (D9): the read path *shows* a raise-or-hold
recommendation, and the target changes only here, on an explicit operator
action, never automatically (the no-auto-modification invariant). Raises the
goal's current target one level up the ladder; a no-op (returns ``None``) when
the goal is absent or already at the top of the ladder.
"""

from __future__ import annotations

from uuid import UUID

from contexts.daily_driver.ports.goal_graph import GoalGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_GOAL_RAISE_TARGET,
    requires_authorisation,
)


@requires_authorisation(DAILY_DRIVER_GOAL_RAISE_TARGET)
async def raise_goal_target(
    *,
    goal_graph: GoalGraphPort,
    actor: ActorContext,
    outcome_id: UUID,
) -> str | None:
    """Raise the goal's current target to the next ladder level (D163).

    Returns the new target level on success, or ``None`` when the goal is
    absent/cross-tenant or already at the top of the ladder.
    """
    goals = await goal_graph.list_goals(tenant_context=actor.tenant_context)
    goal = next((g for g in goals if g.id == outcome_id), None)
    if goal is None or goal.ladder is None:
        return None
    next_target = goal.ladder.next_target
    if next_target is None:
        return None
    return await goal_graph.raise_target_level(
        tenant_context=actor.tenant_context,
        outcome_id=outcome_id,
        commitment_id=goal.lever_commitment_id,
        new_target_level=next_target,
    )


__all__ = ["raise_goal_target"]
