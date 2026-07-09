"""Demand-requirement proof use cases (S103ah, D240): confirm / dismiss / edit / add
each read-modify-write the stored list. Exercised against a stateful fake graph (real
persisted state, not a fresh mock — the S103af idempotent-writes discipline)."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from contexts.daily_driver.application.demand_requirements import (
    add_requirement,
    confirm_requirement,
    dismiss_requirement,
    edit_requirement,
    read_demand_requirements,
)
from contexts.daily_driver.domain import demand_requirements as dr
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import authorisations_for_roles

_TENANT = "00000000-0000-4000-8000-00000000a001"
_OTHER = "00000000-0000-4000-8000-00000000b002"


def _actor(tenant=_TENANT) -> ActorContext:
    roles = frozenset({"operator"})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=tenant, jurisdiction="eu-west", cost_attribution_id=tenant
        ),
        actor_id="operator-001", role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


class _StatefulGraph:
    """A per-tenant persisted requirements store — a second write sees the first."""

    def __init__(self) -> None:
        self.store: dict[tuple, str] = {}

    async def read_opportunity_requirements(self, *, tenant_context, opportunity_id):
        return self.store.get((str(tenant_context.tenant_id), str(opportunity_id)))

    async def set_opportunity_requirements(self, *, tenant_context, opportunity_id, requirements_json):
        self.store[(str(tenant_context.tenant_id), str(opportunity_id))] = requirements_json
        return True

    async def read_opportunity_match(self, *, tenant_context, opportunity_id):
        # the per-opportunity read the enriched view (D241) reads: requirements + JD + match
        key = (str(tenant_context.tenant_id), str(opportunity_id))
        if key not in self.store:
            return None
        return {
            "demand_requirements": self.store[key],
            "job_description": None,
            "match_result": None,
        }


def _seed(graph, opp, items, tenant=_TENANT):
    graph.store[(tenant, str(opp))] = dr.serialize(items)


def _run(coro):
    return asyncio.run(coro)


def test_confirm_then_edit_survive_a_reread() -> None:
    graph, opp = _StatefulGraph(), uuid4()
    drafts = dr.parse_extracted([
        {"text": "Python", "importance": "essential"},
        {"text": "Kafka", "importance": "preferred"},
    ])
    _seed(graph, opp, drafts)
    py_id = drafts[0]["id"]
    # confirm Python
    _run(confirm_requirement(goal_graph=graph, actor=_actor(), opportunity_id=opp, requirement_id=py_id))
    # edit Kafka
    kafka_id = drafts[1]["id"]
    _run(edit_requirement(
        goal_graph=graph, actor=_actor(), opportunity_id=opp, requirement_id=kafka_id,
        text="Kafka & streaming", importance="essential",
    ))
    # re-read reflects both, against real persisted state
    items = _run(read_demand_requirements(goal_graph=graph, actor=_actor(), opportunity_id=opp))
    by_text = {r["text"]: r for r in items}
    assert by_text["Python"]["proof_state"] == "confirmed"
    assert "Kafka & streaming" in by_text and by_text["Kafka & streaming"]["proof_state"] == "confirmed"
    assert "Kafka" not in by_text  # the pre-edit text is gone


def test_dismiss_removes_and_add_appends() -> None:
    graph, opp = _StatefulGraph(), uuid4()
    drafts = dr.parse_extracted([{"text": "A", "importance": "essential"}])
    _seed(graph, opp, drafts)
    _run(dismiss_requirement(goal_graph=graph, actor=_actor(), opportunity_id=opp, requirement_id=drafts[0]["id"]))
    after = _run(add_requirement(goal_graph=graph, actor=_actor(), opportunity_id=opp, text="B", importance="preferred"))
    assert [r["text"] for r in after] == ["B"]
    assert after[0]["proof_state"] == "confirmed"


def test_tenant_isolation_a_write_does_not_leak_across_tenants() -> None:
    graph, opp = _StatefulGraph(), uuid4()
    _run(add_requirement(goal_graph=graph, actor=_actor(_TENANT), opportunity_id=opp, text="Secret req", importance="essential"))
    # the other tenant reading the same opportunity id sees nothing
    other = _run(read_demand_requirements(goal_graph=graph, actor=_actor(_OTHER), opportunity_id=opp))
    assert other == ()
