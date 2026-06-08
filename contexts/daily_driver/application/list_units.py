"""list_units use case — read the correlated work units for display (D168, D166).

Reads the persisted units from the graph (``UnitGraphPort``, thin references)
and joins each facet reference back to its cache projection (via the
``FacetSource``, which the stores decrypt on read) to recover the title + time
the surface renders. The graph is the source of truth for *what is correlated*
(including operator-surfaced candidates); the caches supply the human content.
The assembly is the pure ``build_unit_views`` domain function.
"""

from __future__ import annotations

from contexts.daily_driver.domain.unit_view import UnitView, build_unit_views
from contexts.daily_driver.ports.facet_source import FacetSource
from contexts.daily_driver.ports.unit_graph import UnitGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_UNITS_READ,
    requires_authorisation,
)


@requires_authorisation(DAILY_DRIVER_UNITS_READ)
async def list_units(
    *,
    unit_graph: UnitGraphPort,
    facet_source: FacetSource,
    actor: ActorContext,
) -> tuple[UnitView, ...]:
    """Return the tenant's correlated units, enriched for display."""
    records = await unit_graph.list_units(tenant_context=actor.tenant_context)
    facets = await facet_source.list_facets(actor=actor)
    facets_by_key = {(f.facet_type, f.facet_id): f for f in facets}
    return build_unit_views(records, facets_by_key)


__all__ = ["list_units"]
