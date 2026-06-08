"""correlate_units use case — recompute the work-unit graph (D168, D166).

Reads every correlation-candidate facet through the ``FacetSource`` consumer
port (the stores decrypt on read, so the matcher sees plaintext titles), runs
the pure ``correlate_facets`` inference, and replaces the tenant's unit subgraph
through the ``UnitGraphPort``. Correlation is *derived state* (D155): the
replace + the deterministic unit identity make this idempotent — re-running over
the same caches yields the same graph.

This never writes back to any source tool (D166; the caches are read-only,
D167): the same-work edge is Padhanam-native, recorded only in the graph. The
operator triggers a recompute (the ops path / a future route); the platform
never auto-correlates silently in a way that mutates a source.
"""

from __future__ import annotations

from uuid import UUID

from contexts.daily_driver.domain.work_unit import (
    DEFAULT_CONFIDENCE_FLOOR,
    DEFAULT_TIME_WINDOW_DAYS,
    correlate_facets,
)
from contexts.daily_driver.ports.facet_source import FacetSource
from contexts.daily_driver.ports.unit_graph import UnitGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_UNITS_CORRELATE,
    requires_authorisation,
)


@requires_authorisation(DAILY_DRIVER_UNITS_CORRELATE)
async def correlate_units(
    *,
    facet_source: FacetSource,
    unit_graph: UnitGraphPort,
    actor: ActorContext,
    confidence_floor: float = DEFAULT_CONFIDENCE_FLOOR,
    time_window_days: int = DEFAULT_TIME_WINDOW_DAYS,
) -> int:
    """Recompute and persist the tenant's work-unit correlation graph.

    Returns the number of units written (a single-facet task counts as a
    degenerate unit, so this is at least the facet count's worth of units when
    nothing correlates).
    """
    facets = await facet_source.list_facets(actor=actor)
    units = correlate_facets(
        facets,
        tenant_id=UUID(str(actor.tenant_context.tenant_id)),
        confidence_floor=confidence_floor,
        time_window_days=time_window_days,
    )
    await unit_graph.replace_units(
        tenant_context=actor.tenant_context, units=units
    )
    return len(units)


__all__ = ["correlate_units"]
