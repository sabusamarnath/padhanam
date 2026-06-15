"""list_units_by_goal use case — the moat view anchored on the goal served (D180).

Reads the units (enriched with cache facet titles), the goals, and the persisted
``SERVES`` edges — the same inputs as ``list_goal_assessment`` — then projects
them through the pure ``group_units_by_goal``: units grouped under the
``:Outcome`` each ``SERVES``, orphan units under one unlinked group, the D175
series-fold applied before grouping. A read-and-render projection over the
existing graph; no graph write (S83).
"""

from __future__ import annotations

from datetime import datetime, timezone

from contexts.daily_driver.domain.facet_suggestion import suggest_missing_facets
from contexts.daily_driver.domain.goal_assessment import (
    GoalGroupedUnits,
    group_units_by_goal,
)
from contexts.daily_driver.domain.unit_view import build_unit_views
from contexts.daily_driver.ports.commitment_repository import (
    CommitmentRepository,
)
from contexts.daily_driver.ports.email_job_search_source import (
    EmailJobSearchSource,
)
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
    email_job_search_source: EmailJobSearchSource | None = None,
    commitment_repository: CommitmentRepository | None = None,
    now: datetime | None = None,
) -> GoalGroupedUnits:
    """Return the tenant's units grouped by the goal each serves (D180).

    When an ``email_job_search_source`` is wired, a goal's job-search email
    units fold to a count by kind and the goal reads active on recent activity
    (D183/S89); otherwise the read is the S83 behaviour unchanged.
    """
    records = await unit_graph.list_units(tenant_context=actor.tenant_context)
    facets = await facet_source.list_facets(actor=actor)
    views = build_unit_views(
        records, {(f.facet_type, f.facet_id): f for f in facets}
    )
    goals = await goal_graph.list_goals(tenant_context=actor.tenant_context)
    edges = await unit_graph.list_goal_edges(
        tenant_context=actor.tenant_context
    )
    email_kinds: dict = {}
    if email_job_search_source is not None:
        for c in await email_job_search_source.list_confirmed(actor=actor):
            email_kinds[c.facet_id] = c.kind
    # D187/S92: the commitment cadence signal for the per-goal status (the
    # homeostatic cadence read). Keyed by commitment id.
    commitment_activities: dict = {}
    if commitment_repository is not None:
        for a in await commitment_repository.list_with_activity(
            tenant_context=actor.tenant_context
        ):
            commitment_activities[a.commitment.id] = a
    # D190/S94: the missing-facet suggestions (D170), placed in-goal by the same
    # SERVES edges — the global suggestion list is gone; they ride the goal.
    goal_served = frozenset(e.unit_id for e in edges)
    suggestions = suggest_missing_facets(views, goal_served)
    return group_units_by_goal(
        views, goals, edges,
        email_kinds=email_kinds,
        now=now or datetime.now(timezone.utc),
        commitment_activities=commitment_activities,
        suggestions=suggestions,
    )


__all__ = ["list_units_by_goal"]
