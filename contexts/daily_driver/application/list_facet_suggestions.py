"""list_facet_suggestions use case — the recommendation engine read (D170, D166).

Reads the units (enriched with cache facet titles/times) and the persisted goal
facets (``SERVES`` edges, D169), then computes the credulity-gated missing-facet
suggestions via the pure ``suggest_missing_facets``: a block for a substantial
task with no time, satellite-work for an event with no task, a candidate task for
an email. Read time only — suggestions are recommendation-shaped, never persisted
or written back. The goal facets supply the credulity gate (only goal-serving
units are considered), so the engine needs the edges but not the goals' detail.
"""

from __future__ import annotations

from contexts.daily_driver.domain.facet_suggestion import (
    FacetSuggestion,
    suggest_missing_facets,
)
from contexts.daily_driver.domain.unit_view import build_unit_views
from contexts.daily_driver.ports.facet_source import FacetSource
from contexts.daily_driver.ports.unit_graph import UnitGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_SUGGESTIONS_READ,
    requires_authorisation,
)


@requires_authorisation(DAILY_DRIVER_SUGGESTIONS_READ)
async def list_facet_suggestions(
    *,
    unit_graph: UnitGraphPort,
    facet_source: FacetSource,
    actor: ActorContext,
) -> tuple[FacetSuggestion, ...]:
    """Return the tenant's missing-facet suggestions (D170)."""
    records = await unit_graph.list_units(tenant_context=actor.tenant_context)
    facets = await facet_source.list_facets(actor=actor)
    views = build_unit_views(
        records, {(f.facet_type, f.facet_id): f for f in facets}
    )
    edges = await unit_graph.list_goal_edges(
        tenant_context=actor.tenant_context
    )
    goal_served = frozenset(e.unit_id for e in edges)
    return suggest_missing_facets(views, goal_served)


__all__ = ["list_facet_suggestions"]
