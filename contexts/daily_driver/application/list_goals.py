"""list_goals use case — read each goal against its lever (S62, D163).

Composes the goal layer (via the ``GoalGraphPort`` consumer port) with the lever
commitments' activity (via the ``CommitmentRepository``) and delegates the
target/progress/gap/raise-or-hold reading to the pure ``build_goal_reading``
domain function. ``now`` is minted here so the domain stays deterministic.
"""

from __future__ import annotations

from datetime import datetime, timezone

from contexts.daily_driver.domain.goal import GoalMode
from contexts.daily_driver.domain.goal_view import (
    ChainReading,
    GoalReading,
    build_chain_reading,
    build_goal_reading,
)
from contexts.daily_driver.ports.commitment_repository import (
    CommitmentRepository,
)
from contexts.daily_driver.ports.goal_graph import GoalGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_GOAL_READ,
    requires_authorisation,
)


def _read_goal(goal, activity_by_id, now) -> GoalReading | ChainReading:
    """Branch on mode — the remedy reads the shape, no shared path (D163).

    A progressive goal gets raise-or-hold; a sequence goal gets unblock-or-drop.
    The two never cross: a cadence goal cannot receive a sequence remedy and a
    sequence goal cannot receive a cadence remedy.
    """
    if goal.mode is GoalMode.SEQUENCE:
        return build_chain_reading(
            goal=goal, activity_by_id=activity_by_id, now=now
        )
    # Progressive (and any other not-yet-instanced cadence mode): raise-or-hold.
    return build_goal_reading(
        goal=goal,
        activity=activity_by_id.get(goal.lever_commitment_id),
        now=now,
    )


@requires_authorisation(DAILY_DRIVER_GOAL_READ)
async def list_goals(
    *,
    goal_graph: GoalGraphPort,
    commitment_repository: CommitmentRepository,
    actor: ActorContext,
) -> tuple[GoalReading | ChainReading, ...]:
    """Read the actor's goals, each against its lever(s) (D163).

    The remedy branches on mode: progressive → raise-or-hold, sequence →
    unblock-or-drop. No shared path crosses the two.
    """
    now = datetime.now(timezone.utc)
    goals = await goal_graph.list_goals(tenant_context=actor.tenant_context)
    activities = await commitment_repository.list_with_activity(
        tenant_context=actor.tenant_context
    )
    activity_by_id = {a.commitment.id: a for a in activities}
    return tuple(_read_goal(goal, activity_by_id, now) for goal in goals)


__all__ = ["list_goals"]
