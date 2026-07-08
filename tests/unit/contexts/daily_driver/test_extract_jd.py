"""extract_jd_qualification — stores the JD, drafts context slots (never a value), and
merges discrete requirement drafts keeping confirmed ones (D236/D240)."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from contexts.daily_driver.application.extract_jd import extract_jd_qualification
from contexts.daily_driver.domain import demand_requirements as dr
from contexts.daily_driver.domain.jd_extraction import ExtractedDemand
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import authorisations_for_roles

_TENANT = "00000000-0000-4000-8000-00000000a001"


def _actor() -> ActorContext:
    roles = frozenset({"operator"})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
        ),
        actor_id="operator-001", role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def _reqs(*pairs) -> tuple[dict, ...]:
    return tuple(
        dr.make_requirement(text=t, importance=i, proof_state=dr.PROOF_DRAFT)
        for t, i in pairs
    )


class _FakeGraph:
    """Records what the extraction writes — DRAFT slots + the JD + the merged
    requirements — and NEVER a qualification value (set_qualification_field). Holds a
    real persisted requirements list so the merge is exercised against prior state."""

    def __init__(self, requirements_json: str | None = None) -> None:
        self.jd: tuple | None = None
        self.drafts: list[tuple] = []
        self.value_writes: list[tuple] = []  # must stay empty
        self.requirements_json = requirements_json

    async def set_opportunity_job_description(self, *, tenant_context, opportunity_id, text):
        self.jd = (tenant_context, opportunity_id, text)
        return True

    async def set_qualification_draft(self, *, tenant_context, opportunity_id, field_key, value):
        self.drafts.append((tenant_context, opportunity_id, field_key, value))
        return True

    async def set_qualification_field(self, *, tenant_context, opportunity_id, field_key, value, touch_only=False):
        self.value_writes.append((field_key, value))  # the guard: never reached
        return True

    async def read_opportunity_requirements(self, *, tenant_context, opportunity_id):
        return self.requirements_json

    async def set_opportunity_requirements(self, *, tenant_context, opportunity_id, requirements_json):
        self.requirements_json = requirements_json
        return True


class _FakeExtractor:
    def __init__(self, result):
        self._result = result
        self.seen: str | None = None

    async def extract(self, *, jd_text):
        self.seen = jd_text
        return self._result


def _run(graph, extractor, text, opp=None):
    return asyncio.run(extract_jd_qualification(
        goal_graph=graph, jd_extractor=extractor, actor=_actor(),
        opportunity_id=opp or uuid4(), jd_text=text,
    ))


def test_stores_jd_drafts_context_and_writes_discrete_requirements_never_a_value() -> None:
    graph = _FakeGraph()
    extractor = _FakeExtractor(ExtractedDemand(
        role_open="backfill", success_measures="ship it",
        requirements=_reqs(("Python", "essential"), ("Distributed systems", "preferred")),
    ))
    opp = uuid4()
    keys = _run(graph, extractor, "  a real job description  ", opp=opp)
    # the two context fields drafted; requirements are NOT context drafts
    assert set(keys) == {"role_open", "success_measures"}
    assert graph.jd[2] == "a real job description"
    assert extractor.seen == "a real job description"
    # THE GUARD: only context DRAFT writes, ZERO value writes
    assert len(graph.drafts) == 2
    assert graph.value_writes == []
    # the requirements landed as a discrete list, all draft (no silent fact)
    stored = dr.deserialize(graph.requirements_json)
    assert [r["text"] for r in stored] == ["Python", "Distributed systems"]
    assert all(r["proof_state"] == "draft" for r in stored)
    assert stored[1]["importance"] == "preferred"
    # tenant isolation
    assert graph.jd[0].tenant_id == _TENANT
    assert all(d[0].tenant_id == _TENANT and d[1] == opp for d in graph.drafts)


def test_reextraction_keeps_confirmed_requirements_and_is_idempotent() -> None:
    # A prior extraction produced two drafts; the operator confirmed one.
    prior = _reqs(("Python", "essential"), ("Kafka", "preferred"))
    prior = dr.confirm(prior, prior[0]["id"])  # confirm "Python"
    graph = _FakeGraph(requirements_json=dr.serialize(prior))
    # Re-extract the same JD (same requirement set).
    extractor = _FakeExtractor(ExtractedDemand(
        role_open=None, success_measures=None,
        requirements=_reqs(("Python", "essential"), ("Kafka", "preferred")),
    ))
    _run(graph, extractor, "jd text")
    merged = dr.deserialize(graph.requirements_json)
    # the confirmed "Python" survived (invariant 4), no duplicate created
    assert len(merged) == 2
    py = [r for r in merged if r["text"] == "Python"][0]
    assert py["proof_state"] == "confirmed"
    # idempotent: re-running again changes nothing
    before = graph.requirements_json
    _run(graph, extractor, "jd text")
    assert dr.deserialize(graph.requirements_json) == dr.deserialize(before)


def test_empty_paste_writes_nothing() -> None:
    graph = _FakeGraph()
    extractor = _FakeExtractor(ExtractedDemand("a", "b", _reqs(("x", "essential"))))
    assert _run(graph, extractor, "   ") == ()
    assert graph.jd is None and graph.drafts == [] and graph.requirements_json is None


def test_non_conforming_model_stores_jd_but_writes_no_drafts_or_requirements() -> None:
    graph = _FakeGraph()
    extractor = _FakeExtractor(None)  # StructuredOutputParseFailure surfaced as None
    assert _run(graph, extractor, "jd text") == ()
    assert graph.jd is not None  # the JD is still stored (durable source)
    assert graph.drafts == [] and graph.value_writes == []
    assert graph.requirements_json is None
