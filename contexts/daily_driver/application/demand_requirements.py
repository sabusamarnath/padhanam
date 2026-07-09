"""Demand-requirement proof use cases (S103ah, D240) — read + the four proof ops.

Each requirement extracted from the JD is a draft-as-suggestion (D236): the operator
proofs it individually (Use / edit / Dismiss) and can add missed ones. Every op is a
read-modify-write of the schemaless ``demand_requirements`` list (D214): read the stored
list, apply the pure domain transform, write the whole list back, and return the fresh
list for the surface to re-render. Only confirmed requirements are matched (D239/D240);
no requirement is a fact until proofed (D200).
"""

from __future__ import annotations

from uuid import UUID

from contexts.daily_driver.domain import criticality as crit
from contexts.daily_driver.domain import demand_requirements as dr
from contexts.daily_driver.ports.goal_graph import GoalGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_CDD_READ,
    DAILY_DRIVER_CDD_WRITE,
    requires_authorisation,
)


async def _load(
    goal_graph: GoalGraphPort, actor: ActorContext, opportunity_id: UUID
) -> tuple[dict, ...]:
    return dr.deserialize(
        await goal_graph.read_opportunity_requirements(
            tenant_context=actor.tenant_context, opportunity_id=opportunity_id,
        )
    )


async def _enriched(
    goal_graph: GoalGraphPort, actor: ActorContext, opportunity_id: UUID
) -> tuple[dict, ...]:
    """The enriched requirement views (S103ai/D241) — each item with its criticality
    resolved (spans → text, coverage band, critical-gap flag) against the addressable
    spec + the D239 match. Read after any write so the surface re-renders coherently."""
    data = await goal_graph.read_opportunity_match(
        tenant_context=actor.tenant_context, opportunity_id=opportunity_id,
    )
    if data is None:
        return ()
    return crit.build_requirement_views(
        dr.deserialize(data.get("demand_requirements")),
        data.get("job_description"),
        data.get("match_result"),
    )


async def _store(
    goal_graph: GoalGraphPort, actor: ActorContext, opportunity_id: UUID,
    items: tuple[dict, ...],
) -> tuple[dict, ...]:
    await goal_graph.set_opportunity_requirements(
        tenant_context=actor.tenant_context, opportunity_id=opportunity_id,
        requirements_json=dr.serialize(items),
    )
    return await _enriched(goal_graph, actor, opportunity_id)


@requires_authorisation(DAILY_DRIVER_CDD_READ)
async def read_demand_requirements(
    *, goal_graph: GoalGraphPort, actor: ActorContext, opportunity_id: UUID,
) -> tuple[dict, ...]:
    """The opportunity's discrete demand requirements (draft + confirmed) with their
    criticality (D241) resolved — the proof surface's enriched view (D240/D241)."""
    return await _enriched(goal_graph, actor, opportunity_id)


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def confirm_requirement(
    *, goal_graph: GoalGraphPort, actor: ActorContext, opportunity_id: UUID,
    requirement_id: str,
) -> tuple[dict, ...]:
    """Use a draft requirement as-is → confirmed (D236). Unknown id is a no-op."""
    items = await _load(goal_graph, actor, opportunity_id)
    return await _store(goal_graph, actor, opportunity_id, dr.confirm(items, requirement_id))


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def dismiss_requirement(
    *, goal_graph: GoalGraphPort, actor: ActorContext, opportunity_id: UUID,
    requirement_id: str,
) -> tuple[dict, ...]:
    """Dismiss a requirement → remove it (D236). Unknown id is a no-op."""
    items = await _load(goal_graph, actor, opportunity_id)
    return await _store(goal_graph, actor, opportunity_id, dr.dismiss(items, requirement_id))


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def edit_requirement(
    *, goal_graph: GoalGraphPort, actor: ActorContext, opportunity_id: UUID,
    requirement_id: str, text: str, importance: str,
) -> tuple[dict, ...]:
    """Edit a requirement's text/importance and confirm it (D236). An empty text or an
    unknown id is a no-op (Dismiss removes)."""
    items = await _load(goal_graph, actor, opportunity_id)
    return await _store(
        goal_graph, actor, opportunity_id,
        dr.edit(items, requirement_id, text=text, importance=importance),
    )


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def add_requirement(
    *, goal_graph: GoalGraphPort, actor: ActorContext, opportunity_id: UUID,
    text: str, importance: str,
) -> tuple[dict, ...]:
    """Add an operator-authored requirement the extraction missed, confirmed (D236). An
    empty text is a no-op; a duplicate confirms the existing item."""
    items = await _load(goal_graph, actor, opportunity_id)
    return await _store(
        goal_graph, actor, opportunity_id, dr.add(items, text=text, importance=importance)
    )


__all__ = [
    "add_requirement",
    "confirm_requirement",
    "dismiss_requirement",
    "edit_requirement",
    "read_demand_requirements",
]
