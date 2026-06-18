"""read_element_evidence — the read-only element-evidence summary (D202, S103b).

Surfaces where matched signal landed: per authored element, how many units
evidence it, plus the unbound-bucket size (units that matched no element — the
emergent loop's queue, S104). Read-only; the relink/unlink correction paths are
S103c. Behind ``CDD_READ`` (the user inspecting their own model's evidence).
"""

from __future__ import annotations

from contexts.daily_driver.domain.goal_assessment import (
    ElementBinding,
    ElementEvidenceSummary,
    summarise_element_evidence,
)
from contexts.daily_driver.domain.unit_view import build_unit_views
from contexts.daily_driver.ports.facet_source import FacetSource
from contexts.daily_driver.ports.unit_graph import UnitGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_CDD_READ,
    requires_authorisation,
)


@requires_authorisation(DAILY_DRIVER_CDD_READ)
async def read_element_evidence(
    *, unit_graph: UnitGraphPort, actor: ActorContext
) -> ElementEvidenceSummary:
    """Return per-element unit counts + the unbound-bucket size (S103b)."""
    evidence = await unit_graph.list_element_evidence(
        tenant_context=actor.tenant_context
    )
    units = await unit_graph.list_units(tenant_context=actor.tenant_context)
    return summarise_element_evidence(evidence, total_units=len(units))


@requires_authorisation(DAILY_DRIVER_CDD_READ)
async def read_element_bindings(
    *, unit_graph: UnitGraphPort, facet_source: FacetSource, actor: ActorContext
) -> tuple[ElementBinding, ...]:
    """Return each unit→element binding joined to the unit's title + its
    user-ownership, so the lens can show bound units under each element with
    relink/unlink affordances (D203, S103c)."""
    evidence = await unit_graph.list_element_evidence(
        tenant_context=actor.tenant_context
    )
    records = await unit_graph.list_units(tenant_context=actor.tenant_context)
    facets = await facet_source.list_facets(actor=actor)
    views = build_unit_views(
        tuple(records), {(f.facet_type, f.facet_id): f for f in facets}
    )
    title_by_unit = {v.unit_id: v.title for v in views}
    owned = await unit_graph.list_user_owned_unit_ids(
        tenant_context=actor.tenant_context
    )
    return tuple(
        ElementBinding(
            unit_id=e.unit_id,
            title=title_by_unit.get(e.unit_id, "(unknown)"),
            element_kind=e.element_kind,
            element_id=e.element_id,
            tier=e.tier,
            user_owned=e.unit_id in owned,
        )
        for e in evidence
    )


__all__ = ["read_element_bindings", "read_element_evidence"]
