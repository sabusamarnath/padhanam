"""The criticality assessment use case (S103ai, D241) — reads JD + requirements, assesses
via the port grounded-strict, stores the criticality on the items; tenant isolation."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from contexts.daily_driver.application.criticality import assess_criticality
from contexts.daily_driver.domain import demand_requirements as dr
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import authorisations_for_roles

_TENANT = "00000000-0000-4000-8000-00000000a001"
_JD = "Essential criteria:\n- Minimum 8 years experience.\n- Strong leadership."


def _actor(tenant=_TENANT) -> ActorContext:
    roles = frozenset({"operator"})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=tenant, jurisdiction="eu-west", cost_attribution_id=tenant
        ),
        actor_id="operator-001", role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


class _FakeGraph:
    def __init__(self, *, jd=_JD, requirements=(), match_result=None):
        self.jd = jd
        self.requirements_json = dr.serialize(requirements)
        self.match_result = match_result
        self.writes = 0
        self.tenants_seen: list[str] = []

    async def read_opportunity_match(self, *, tenant_context, opportunity_id):
        self.tenants_seen.append(tenant_context.tenant_id)
        return {
            "demand_requirements": self.requirements_json,
            "job_description": self.jd,
            "match_result": self.match_result,
        }

    async def set_opportunity_requirements(self, *, tenant_context, opportunity_id, requirements_json):
        self.tenants_seen.append(tenant_context.tenant_id)
        self.requirements_json = requirements_json
        self.writes += 1
        return True


class _FakePort:
    """Returns a criticality keyed by normalized requirement text (already parsed
    grounded-strict — the adapter's job); ``None`` simulates a non-conforming model."""

    def __init__(self, result):
        self._result = result
        self.seen = None

    async def assess(self, *, requirement_texts, spec_index):
        self.seen = (requirement_texts, spec_index)
        return self._result


def _reqs():
    return dr.parse_extracted([
        {"text": "Minimum 8 years experience", "importance": "essential"},
        {"text": "Strong leadership", "importance": "preferred"},
    ])


def _run(graph, port, tenant=_TENANT):
    return asyncio.run(assess_criticality(
        goal_graph=graph, criticality_port=port, actor=_actor(tenant),
        opportunity_id=uuid4(),
    ))


def test_assess_stores_criticality_on_the_items() -> None:
    graph = _FakeGraph(requirements=_reqs())
    port = _FakePort({
        "minimum 8 years experience": {"explanation": "a hard bar", "hard_gate": True,
                                        "spans": ["sec-0"], "confidence": "high"},
    })
    views = _run(graph, port)
    # the port saw the requirement texts + a real spec index
    assert set(port.seen[0]) == {"Minimum 8 years experience", "Strong leadership"}
    assert not port.seen[1].is_empty()
    # criticality was written back onto the item and survives in the store
    stored = dr.deserialize(graph.requirements_json)
    hit = [r for r in stored if r["text"] == "Minimum 8 years experience"][0]
    assert hit["criticality"]["hard_gate"] is True
    # the returned view carries the resolved criticality
    v = [v for v in views if v["text"] == "Minimum 8 years experience"][0]
    assert v["criticality"] == "a hard bar" and v["hard_gate"] is True
    assert graph.writes == 1
    assert set(graph.tenants_seen) == {_TENANT}


def test_no_jd_assesses_nothing() -> None:
    graph = _FakeGraph(jd=None, requirements=_reqs())
    port = _FakePort({"x": {}})
    _run(graph, port)
    assert graph.writes == 0          # no addressable spec → nothing assessed
    assert port.seen is None          # the port was never called


def test_non_conforming_model_persists_nothing() -> None:
    graph = _FakeGraph(requirements=_reqs())
    port = _FakePort(None)            # StructuredOutputParseFailure surfaced as None
    _run(graph, port)
    assert graph.writes == 0


def test_critical_gap_flagged_from_the_stored_match() -> None:
    match = '[{"criterion": "Minimum 8 years experience", "band": "gap", "evidence": ""}]'
    graph = _FakeGraph(requirements=_reqs(), match_result=match)
    port = _FakePort({
        "minimum 8 years experience": {"explanation": "a hard bar", "hard_gate": True,
                                        "spans": ["sec-0"], "confidence": "high"},
    })
    views = _run(graph, port)
    v = [v for v in views if v["text"] == "Minimum 8 years experience"][0]
    assert v["critical_gap"] is True   # gap on a hard-gate requirement
