"""Requirement-criticality assessment use case (S103ai, D241).

Reads the opportunity's stored demand spec (JD, D236) + its discrete requirements (D240),
indexes the spec into addressable spans (``demand_spec``), calls the ``CriticalityPort``
(the LiteLLM seam) for a reasoned, span-linked criticality per requirement — grounded-
strict (references validated to resolve, ungrounded claims forced low-confidence) — and
writes the assessment back onto each requirement item. Returns the enriched requirement
views (criticality resolved to text + coverage band + critical-gap flag) for the surface.
"""

from __future__ import annotations

from uuid import UUID

from contexts.daily_driver.domain import criticality as crit
from contexts.daily_driver.domain import demand_requirements as dr
from contexts.daily_driver.domain.demand_spec import index_demand_spec
from contexts.daily_driver.ports.criticality import CriticalityPort
from contexts.daily_driver.ports.goal_graph import GoalGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_CDD_WRITE,
    requires_authorisation,
)


def _views(data: dict) -> tuple[dict, ...]:
    return crit.build_requirement_views(
        dr.deserialize(data.get("demand_requirements")),
        data.get("job_description"),
        data.get("match_result"),
    )


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def assess_criticality(
    *, goal_graph: GoalGraphPort, criticality_port: CriticalityPort,
    actor: ActorContext, opportunity_id: UUID,
) -> tuple[dict, ...]:
    """Assess each requirement's criticality against the addressable demand spec (D241)
    and store it on the requirement items. Returns the enriched views. ``()`` when the
    opportunity is absent; the current views (unchanged) when there is no JD, no
    requirements, or the model returns nothing conforming."""
    data = await goal_graph.read_opportunity_match(
        tenant_context=actor.tenant_context, opportunity_id=opportunity_id,
    )
    if data is None:
        return ()
    items = dr.deserialize(data.get("demand_requirements"))
    index = index_demand_spec(data.get("job_description"))
    if not items or index.is_empty():
        return _views(data)  # nothing to assess (no requirements or no addressable spec)

    texts = tuple(i["text"] for i in items)
    assessed = await criticality_port.assess(
        requirement_texts=texts, spec_index=index,
    )
    if assessed is None:
        return _views(data)  # non-conforming — persist nothing, return current

    merged = crit.attach_criticality(items, assessed)
    await goal_graph.set_opportunity_requirements(
        tenant_context=actor.tenant_context, opportunity_id=opportunity_id,
        requirements_json=dr.serialize(merged),
    )
    fresh = await goal_graph.read_opportunity_match(
        tenant_context=actor.tenant_context, opportunity_id=opportunity_id,
    )
    return _views(fresh or data)


__all__ = ["assess_criticality"]
