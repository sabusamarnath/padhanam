"""extract_cv_profile — parses the CV and seeds SUGGESTED items, never confirmed;
a no-text-layer PDF seeds nothing and flags re-export (S103af, D238)."""

from __future__ import annotations

import asyncio

from contexts.daily_driver.application.extract_cv import extract_cv_profile
from contexts.daily_driver.domain.cv import ParsedCv
from contexts.daily_driver.domain.cv_extraction import ExtractedProfile, skill_item_id
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
    """Records seeds. The guard: extraction seeds via seed_skill_item (suggested),
    NEVER create_skill_item (confirmed)."""

    def __init__(self) -> None:
        self.seeds: list[tuple] = []
        self.creates: list[tuple] = []  # must stay empty

    async def seed_skill_item(self, *, tenant_context, item_id, kind, text):
        self.seeds.append((tenant_context, item_id, kind, text))

    async def create_skill_item(self, *, tenant_context, item_id, kind, text):
        self.creates.append((kind, text))


class _FakeParser:
    def __init__(self, parsed):
        self._parsed = parsed
        self.seen: bytes | None = None

    async def parse(self, *, pdf_bytes):
        self.seen = pdf_bytes
        return self._parsed


class _FakeExtractor:
    def __init__(self, result):
        self._result = result
        self.seen: str | None = None

    async def extract(self, *, cv_text):
        self.seen = cv_text
        return self._result


def _run(parser, extractor, graph, pdf=b"%PDF-fake"):
    return asyncio.run(extract_cv_profile(
        goal_graph=graph, cv_parser=parser, cv_extractor=extractor,
        actor=_actor(), pdf_bytes=pdf,
    ))


def test_seeds_each_item_suggested_never_confirmed_with_deterministic_ids() -> None:
    graph = _FakeGraph()
    parser = _FakeParser(ParsedCv(text="cv text", has_text_layer=True, page_count=2))
    extractor = _FakeExtractor(ExtractedProfile(skills=("SQL", "Python"), experiences=("Led a team",)))
    result = _run(parser, extractor, graph)
    assert result.seeded == 3
    assert result.needs_text_layer is False
    assert result.page_count == 2
    # the extractor saw the parsed text
    assert extractor.seen == "cv text"
    # THE GUARD: three seeds (suggested), zero confirmed creates
    assert len(graph.seeds) == 3
    assert graph.creates == []
    # ids are deterministic (uuid5 over kind+text), tenant carried
    assert graph.seeds[0][1] == skill_item_id("skill", "SQL")
    assert graph.seeds[2][1] == skill_item_id("experience", "Led a team")
    assert all(s[0].tenant_id == _TENANT for s in graph.seeds)


def test_no_text_layer_seeds_nothing_and_flags_re_export() -> None:
    graph = _FakeGraph()
    parser = _FakeParser(ParsedCv(text="", has_text_layer=False, page_count=1))
    extractor = _FakeExtractor(ExtractedProfile(skills=("SQL",), experiences=()))
    result = _run(parser, extractor, graph)
    assert result.needs_text_layer is True
    assert result.seeded == 0
    assert graph.seeds == []
    # the extractor was never called (no text to extract from)
    assert extractor.seen is None


def test_non_conforming_model_seeds_nothing() -> None:
    graph = _FakeGraph()
    parser = _FakeParser(ParsedCv(text="cv text", has_text_layer=True, page_count=1))
    extractor = _FakeExtractor(None)  # StructuredOutputParseFailure surfaced as None
    result = _run(parser, extractor, graph)
    assert result.seeded == 0
    assert result.needs_text_layer is False
    assert graph.seeds == []
