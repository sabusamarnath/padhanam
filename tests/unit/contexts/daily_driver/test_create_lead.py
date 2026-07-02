"""S103t/D221: the create-lead use case — author a user-authored :Opportunity at
the goal's Lead gate.

Fake GoalGraphPort — asserts the use case validates the three origination
vocabularies, resolves the Lead gate by name, and writes with user_authored
provenance at that gate. No live graph, no PII.
"""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest

from contexts.daily_driver.application.create_lead import (
    LeadValidationError,
    create_lead,
)
from contexts.daily_driver.domain.cdd import (
    GateView,
    GoalCddView,
    ProofState,
    ProvenanceOrigin,
)
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles

_TENANT = "00000000-0000-4000-8000-00000000d001"
_OUTCOME = UUID("00000000-0000-4000-8000-0000006300a1")
_LEAD_GATE = UUID("00000000-0000-4000-8000-0000063a0000")
_APPLY_GATE = UUID("00000000-0000-4000-8000-0000063a0001")


def _actor() -> ActorContext:
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
        ),
        actor_id="operator-001",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def _gate(name: str, gate_id: UUID, order: int) -> GateView:
    return GateView(
        gate_id=gate_id, name=name, gate_order=order, local_outcome="",
        local_goal="", provenance_origin=ProvenanceOrigin.LLM_DRAFTED,
        proof_state=ProofState.PENDING, step_commitment_id=None,
    )


class _FakeGoalGraph:
    def __init__(self, *, gates):
        self._gates = gates
        self.created = None

    async def read_goal_cdd(self, *, tenant_context, outcome_id):
        return GoalCddView(
            outcome_id=outcome_id, expected_outcome="", elements=(), edges=(),
            gates=self._gates,
        )

    async def create_lead(self, *, tenant_context, opportunity_id, outcome_id,
                          name, lead_gate_id, fit_tier, warm_access_available,
                          origination_source):
        self.created = dict(
            tenant_id=tenant_context.tenant_id, opportunity_id=opportunity_id,
            outcome_id=outcome_id, name=name, lead_gate_id=lead_gate_id,
            fit_tier=fit_tier, warm_access_available=warm_access_available,
            origination_source=origination_source,
        )


_GATES = (
    _gate("Lead", _LEAD_GATE, 2),
    _gate("Apply", _APPLY_GATE, 3),
)


def test_create_lead_writes_user_authored_at_the_lead_gate():
    graph = _FakeGoalGraph(gates=_GATES)

    async def run():
        return await create_lead(
            goal_graph=graph, actor=_actor(), outcome_id=_OUTCOME,
            company="BigBank", role="VP Product", fit_tier="bullseye",
            warm_access_available="warm", origination_source="inbound",
        )

    oid = asyncio.run(run())
    assert isinstance(oid, UUID)
    c = graph.created
    assert c is not None
    assert c["lead_gate_id"] == _LEAD_GATE          # resolved by name, below Apply
    assert c["name"] == "BigBank — VP Product"       # company — role
    assert c["fit_tier"] == "bullseye"
    assert c["warm_access_available"] == "warm"
    assert c["origination_source"] == "inbound"
    assert c["tenant_id"] == _TENANT                 # tenant-scoped


def test_create_lead_name_is_company_only_when_role_blank():
    graph = _FakeGoalGraph(gates=_GATES)

    async def run():
        await create_lead(
            goal_graph=graph, actor=_actor(), outcome_id=_OUTCOME,
            company="Acme", role="  ", fit_tier="strong",
            warm_access_available="cold", origination_source="outbound",
        )

    asyncio.run(run())
    assert graph.created["name"] == "Acme"


@pytest.mark.parametrize("bad", [
    dict(fit_tier="unicorn", warm_access_available="warm", origination_source="inbound"),
    dict(fit_tier="bullseye", warm_access_available="lukewarm", origination_source="inbound"),
    dict(fit_tier="bullseye", warm_access_available="warm", origination_source="carrier-pigeon"),
    dict(fit_tier="bullseye", warm_access_available="warm", origination_source="inbound", company="  "),
])
def test_create_lead_rejects_bad_vocabulary(bad):
    graph = _FakeGoalGraph(gates=_GATES)
    company = bad.pop("company", "Acme")

    async def run():
        await create_lead(
            goal_graph=graph, actor=_actor(), outcome_id=_OUTCOME,
            company=company, role="R", **bad,
        )

    with pytest.raises(LeadValidationError):
        asyncio.run(run())
    assert graph.created is None                      # no write on a bad field


def test_create_lead_requires_a_lead_gate():
    # A goal without a seeded Lead gate cannot originate — the use case refuses
    # rather than writing a lead with no gate.
    graph = _FakeGoalGraph(gates=(_gate("Apply", _APPLY_GATE, 3),))

    async def run():
        await create_lead(
            goal_graph=graph, actor=_actor(), outcome_id=_OUTCOME,
            company="Acme", role="R", fit_tier="bullseye",
            warm_access_available="warm", origination_source="inbound",
        )

    with pytest.raises(LeadValidationError):
        asyncio.run(run())
    assert graph.created is None
