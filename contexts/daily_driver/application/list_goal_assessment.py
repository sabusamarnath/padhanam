"""list_goal_assessment use case — the two moat reads for display (D169, D166).

Reads the units (enriched with cache facet titles), the goals, and the persisted
``SERVES`` edges, then computes the two recommendation-shaped reads via the pure
``assess_goals``: **orphan work** (a unit pointing at no goal) and the
**neglected goal** (a goal nothing points at). The goal edges are the source of
truth for what is correlated to a goal (including operator-surfaced candidates);
the assessment reads that, it does not re-infer.
"""

from __future__ import annotations

from contexts.daily_driver.domain.goal_assessment import (
    GoalAssessment,
    assess_goals,
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
async def list_goal_assessment(
    *,
    unit_graph: UnitGraphPort,
    facet_source: FacetSource,
    goal_graph: GoalGraphPort,
    actor: ActorContext,
) -> GoalAssessment:
    """Return the tenant's orphan-work + neglected-goal reads (D169)."""
    records = await unit_graph.list_units(tenant_context=actor.tenant_context)
    facets = await facet_source.list_facets(actor=actor)
    views = build_unit_views(
        records, {(f.facet_type, f.facet_id): f for f in facets}
    )
    goals = await goal_graph.list_goals(tenant_context=actor.tenant_context)
    edges = await unit_graph.list_goal_edges(
        tenant_context=actor.tenant_context
    )
    return assess_goals(views, goals, edges)


__all__ = ["list_goal_assessment"]
