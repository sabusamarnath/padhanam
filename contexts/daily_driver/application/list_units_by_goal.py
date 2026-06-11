"""list_units_by_goal use case — the moat view anchored on the goal served (D180).

Reads the units (enriched with cache facet titles), the goals, and the persisted
``SERVES`` edges — the same inputs as ``list_goal_assessment`` — then projects
them through the pure ``group_units_by_goal``: units grouped under the
``:Outcome`` each ``SERVES``, orphan units under one unlinked group, the D175
series-fold applied before grouping. A read-and-render projection over the
existing graph; no graph write (S83).
"""

from __future__ import annotations

from contexts.daily_driver.domain.goal_assessment import (
    GoalGroupedUnits,
    group_units_by_goal,
)
from contexts.daily_driver.domain.unit_view import build_unit_views
from contexts.daily_driver.ports.facet_source import FacetSource
from contexts.daily_driver.ports.goal_graph import GoalGraphPort
from contexts.daily_driver.ports.unit_graph import UnitGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_ASSESSMENT_READ,
    requires_authorisation,
)


@requires_authorisation(DAILY_DRIVER_ASSESSMENT_READ)
async def list_units_by_goal(
    *,
    unit_graph: UnitGraphPort,
    facet_source: FacetSource,
    goal_graph: GoalGraphPort,
    actor: ActorContext,
) -> GoalGroupedUnits:
    """Return the tenant's units grouped by the goal each serves (D180)."""
    records = await unit_graph.list_units(tenant_context=actor.tenant_context)
    facets = await facet_source.list_facets(actor=actor)
    views = build_unit_views(
        records, {(f.facet_type, f.facet_id): f for f in facets}
    )
    goals = await goal_graph.list_goals(tenant_context=actor.tenant_context)
    edges = await unit_graph.list_goal_edges(
        tenant_context=actor.tenant_context
    )
    return group_units_by_goal(views, goals, edges)


__all__ = ["list_units_by_goal"]
