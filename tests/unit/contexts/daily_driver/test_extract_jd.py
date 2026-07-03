"""extract_jd_qualification — stores the JD, drafts to slots, never a value (D236)."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from contexts.daily_driver.application.extract_jd import extract_jd_qualification
from contexts.daily_driver.domain.jd_extraction import ExtractedQualification
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


class _FakeGraph:
    """Records what the extraction writes — crucially, that it writes DRAFT slots and
    the JD, and NEVER a qualification value (set_qualification_field)."""

    def __init__(self) -> None:
        self.jd: tuple | None = None
        self.drafts: list[tuple] = []
        self.value_writes: list[tuple] = []  # must stay empty

    async def set_opportunity_job_description(self, *, tenant_context, opportunity_id, text):
        self.jd = (tenant_context, opportunity_id, text)
        return True

    async def set_qualification_draft(self, *, tenant_context, opportunity_id, field_key, value):
        self.drafts.append((tenant_context, opportunity_id, field_key, value))
        return True

    async def set_qualification_field(self, *, tenant_context, opportunity_id, field_key, value, touch_only=False):
        self.value_writes.append((field_key, value))  # the guard: never reached
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


def test_stores_jd_and_writes_three_draft_slots_never_a_value() -> None:
    graph = _FakeGraph()
    extractor = _FakeExtractor(ExtractedQualification(
        role_open="backfill", success_measures="ship it", selection_criteria="python",
    ))
    opp = uuid4()
    keys = _run(graph, extractor, "  a real job description  ", opp=opp)
    assert set(keys) == {"role_open", "success_measures", "selection_criteria"}
    # the JD was stored (trimmed), and the extractor saw the trimmed text
    assert graph.jd[2] == "a real job description"
    assert extractor.seen == "a real job description"
    # THE GUARD: three DRAFT writes, ZERO value writes — no field holds an unproofed value
    assert len(graph.drafts) == 3
    assert graph.value_writes == []
    # tenant isolation: every write carried the actor's tenant_context
    assert graph.jd[0].tenant_id == _TENANT
    assert all(d[0].tenant_id == _TENANT and d[1] == opp for d in graph.drafts)


def test_partial_extract_writes_only_the_stated_fields() -> None:
    graph = _FakeGraph()
    extractor = _FakeExtractor(ExtractedQualification(
        role_open="backfill", success_measures=None, selection_criteria=None,
    ))
    keys = _run(graph, extractor, "jd text")
    assert keys == ("role_open",)
    assert len(graph.drafts) == 1 and graph.value_writes == []


def test_empty_paste_writes_nothing() -> None:
    graph = _FakeGraph()
    extractor = _FakeExtractor(ExtractedQualification("a", "b", "c"))
    assert _run(graph, extractor, "   ") == ()
    assert graph.jd is None and graph.drafts == [] and graph.value_writes == []


def test_non_conforming_model_stores_jd_but_writes_no_drafts() -> None:
    graph = _FakeGraph()
    extractor = _FakeExtractor(None)  # StructuredOutputParseFailure surfaced as None
    assert _run(graph, extractor, "jd text") == ()
    assert graph.jd is not None  # the JD is still stored (durable source for leg 3)
    assert graph.drafts == [] and graph.value_writes == []
