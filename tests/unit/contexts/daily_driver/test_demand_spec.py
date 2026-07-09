"""The addressable demand spec — deterministic coarse indexing + resolution (S103ai, D241)."""

from __future__ import annotations

from contexts.daily_driver.domain.demand_spec import (
    MAX_SPEC_CHARS,
    index_demand_spec,
    resolve_spans,
    spans_for_prompt,
)


def _jd() -> str:
    return (
        "Director of AI. About the role: we scale AI adoption.\n\n"
        "Essential criteria:\n- Minimum 8 years experience. A required certification.\n"
        "- Strong stakeholder skills."
    )


def test_indexes_sections_and_sentences_with_stable_ids() -> None:
    idx = index_demand_spec(_jd())
    ids = idx.ids()
    assert "sec-0" in ids and "sec-1" in ids       # two blank-line blocks
    assert "sent-0" in ids                          # sentences numbered globally
    # deterministic: same text → same ids
    assert index_demand_spec(_jd()).ids() == ids


def test_resolve_and_non_resolving() -> None:
    idx = index_demand_spec(_jd())
    assert idx.resolve("sec-0").startswith("Director of AI")
    assert idx.resolve("sec-99") is None            # a hallucinated / stale id
    assert idx.resolve("nonsense") is None


def test_resolve_spans_drops_non_resolving_and_dedups() -> None:
    idx = index_demand_spec(_jd())
    got = resolve_spans(idx, ("sec-0", "sec-99", "sec-0", "sent-1"))
    ids = [s.id for s in got]
    assert "sec-99" not in ids                       # dropped (does not resolve)
    assert ids.count("sec-0") == 1                   # deduped
    assert "sent-1" in ids
    assert all(s.text for s in got)                  # each carries its text
    assert {s.kind for s in got} <= {"section", "sentence"}


def test_empty_or_blank_yields_empty_index() -> None:
    assert index_demand_spec(None).is_empty()
    assert index_demand_spec("   \n  ").is_empty()
    assert resolve_spans(index_demand_spec(None), ("sec-0",)) == ()


def test_prompt_render_lists_ids_and_caps_the_input() -> None:
    idx = index_demand_spec(_jd())
    rendered = spans_for_prompt(idx)
    assert "[sec-0]" in rendered and "[sent-0]" in rendered
    # the input text is capped before indexing so a huge paste cannot blow up the index
    big = index_demand_spec("word. " * (MAX_SPEC_CHARS))   # far more than the cap
    indexed_chars = sum(len(s.text) for s in big.spans if s.kind == "section")
    assert indexed_chars <= MAX_SPEC_CHARS
