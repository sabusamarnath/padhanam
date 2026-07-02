"""create_lead — author a new lead at the Lead gate (S103t, D221).

Origination becomes first-class: a new lead is a ``user_authored`` ``:Opportunity``
created directly at the goal's Lead gate (the origination stage below Apply), with
zero touches and no correspondence thread. It carries the three operator-set
origination properties — ``fit_tier`` (bullseye/strong/opportunistic),
``warm_access_available`` (warm/cold), ``origination_source`` (inbound/outbound) —
which the operator sets by reading the authored fit rubric (assess-not-replace,
D200; the platform does not auto-score). The write reuses the D215
``merge_opportunity`` path via ``GoalGraphPort.create_lead``; the apply-advance
(Lead -> Apply) reuses ``set_opportunity_gate`` (S103q), so no new advance path is
needed here.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from contexts.daily_driver.ports.goal_graph import GoalGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_CDD_WRITE,
    requires_authorisation,
)

# The origination vocabularies (D221). "Below tier" is not originated, so it is not
# a valid fit_tier for a created lead — a below-tier target is simply not a lead.
FIT_TIERS = ("bullseye", "strong", "opportunistic")
WARM_ACCESS = ("warm", "cold")
ORIGINATION_SOURCES = ("inbound", "outbound")
_LEAD_GATE_NAME = "Lead"


class LeadValidationError(ValueError):
    """A lead field is outside its allowed vocabulary, the company is empty, or the
    goal has no Lead gate to originate into."""


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def create_lead(
    *,
    goal_graph: GoalGraphPort,
    actor: ActorContext,
    outcome_id: UUID,
    company: str,
    role: str,
    fit_tier: str,
    warm_access_available: str,
    origination_source: str,
) -> UUID:
    """Create a ``user_authored`` lead ``:Opportunity`` at the goal's Lead gate
    (D221). Validates the three origination vocabularies, resolves the Lead gate by
    name from the goal's CDD, and returns the new opportunity's id. Raises
    ``LeadValidationError`` on a bad field or a missing Lead gate."""
    company = company.strip()
    if not company:
        raise LeadValidationError("company is required")
    if fit_tier not in FIT_TIERS:
        raise LeadValidationError(f"fit_tier must be one of {list(FIT_TIERS)}")
    if warm_access_available not in WARM_ACCESS:
        raise LeadValidationError("warm_access_available must be 'warm' or 'cold'")
    if origination_source not in ORIGINATION_SOURCES:
        raise LeadValidationError(
            "origination_source must be 'inbound' or 'outbound'"
        )

    cdd = await goal_graph.read_goal_cdd(
        tenant_context=actor.tenant_context, outcome_id=outcome_id
    )
    lead_gate = next((g for g in cdd.gates if g.name == _LEAD_GATE_NAME), None)
    if lead_gate is None:
        raise LeadValidationError(
            "the goal has no Lead gate — seed the gates first (make seed-get-a-job-gates)"
        )

    role = role.strip()
    name = f"{company} — {role}" if role else company
    opportunity_id = uuid4()
    await goal_graph.create_lead(
        tenant_context=actor.tenant_context,
        opportunity_id=opportunity_id,
        outcome_id=outcome_id,
        name=name,
        lead_gate_id=lead_gate.gate_id,
        fit_tier=fit_tier,
        warm_access_available=warm_access_available,
        origination_source=origination_source,
    )
    return opportunity_id


__all__ = [
    "create_lead",
    "LeadValidationError",
    "FIT_TIERS",
    "WARM_ACCESS",
    "ORIGINATION_SOURCES",
]
