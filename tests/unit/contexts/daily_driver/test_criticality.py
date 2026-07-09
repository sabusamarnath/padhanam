"""Requirement criticality — config-driven schema, grounded-strict parse, honest
low-confidence, and critical-gap flagging (S103ai, D241)."""

from __future__ import annotations

from contexts.daily_driver.domain import criticality as crit
from contexts.daily_driver.domain import demand_requirements as dr
from contexts.daily_driver.domain.demand_spec import index_demand_spec

_JD = "Essential criteria:\n- Minimum 8 years experience.\n- Strong leadership."


def _idx():
    return index_demand_spec(_JD)


def _req(text, importance="essential", proof="confirmed"):
    return dr.make_requirement(text=text, importance=importance, proof_state=proof)


def test_schema_is_config_driven_from_criticality_fields() -> None:
    schema = crit.criticality_batch_schema(("A",))
    item = schema["properties"]["assessments"]["items"]
    keys = {k for k, *_ in crit.CRITICALITY_FIELDS}
    assert keys <= set(item["properties"])                 # every config field present
    assert "requirement" in item["properties"]             # the map-back key
    assert item["properties"]["confidence"]["enum"] == list(crit.CONFIDENCE_LEVELS)
    assert item["additionalProperties"] is False


def test_parse_drops_hallucinated_spans_and_keeps_resolving_ones() -> None:
    idx = _idx()
    val = {"assessments": [
        {"requirement": "Minimum 8 years", "explanation": "a hard bar",
         "hard_gate": True, "spans": ["sec-0", "sent-99"], "confidence": "high"},
    ]}
    parsed = crit.parse_criticality(("Minimum 8 years",), idx, val)
    c = parsed["minimum 8 years"]
    assert c["spans"] == ["sec-0"]          # sent-99 (does not resolve) dropped
    assert c["hard_gate"] is True
    assert c["confidence"] == "high"        # a resolving span remains → confidence stands


def test_ungrounded_claim_is_forced_low_confidence() -> None:
    # every cited span is hallucinated → no evidence → honest low-confidence, empty spans
    idx = _idx()
    val = {"assessments": [
        {"requirement": "Strong leadership", "explanation": "senior roles usually need this",
         "hard_gate": False, "spans": ["sec-42"], "confidence": "high"},
    ]}
    c = crit.parse_criticality(("Strong leadership",), idx, val)["strong leadership"]
    assert c["spans"] == []
    assert c["confidence"] == "low"


def test_parse_drops_non_input_and_empty_explanation() -> None:
    idx = _idx()
    val = {"assessments": [
        {"requirement": "Invented", "explanation": "x", "hard_gate": False, "spans": ["sec-0"], "confidence": "high"},
        {"requirement": "Minimum 8 years", "explanation": "  ", "hard_gate": False, "spans": ["sec-0"], "confidence": "high"},
    ]}
    parsed = crit.parse_criticality(("Minimum 8 years",), idx, val)
    assert "invented" not in parsed          # not an input requirement → dropped
    assert "minimum 8 years" not in parsed   # empty explanation → dropped


def test_confidence_defaults_low_when_unknown() -> None:
    idx = _idx()
    val = {"assessments": [
        {"requirement": "Minimum 8 years", "explanation": "clear", "hard_gate": False,
         "spans": ["sec-0"], "confidence": "unspecified-nonsense"},
    ]}
    assert crit.parse_criticality(("Minimum 8 years",), idx, val)["minimum 8 years"]["confidence"] == "low"


def test_critical_gap_combines_criticality_and_coverage() -> None:
    hard = _req("A"); hard["criticality"] = {"hard_gate": True}
    essential = _req("B", importance="essential")
    preferred = _req("C", importance="preferred")
    # gap on a hard gate or an essential → critical; gap on a preferred → not
    assert crit.critical_gap(hard, "gap") is True
    assert crit.critical_gap(essential, "gap") is True
    assert crit.critical_gap(preferred, "gap") is False
    # a thin partial on a hard gate is still critical; partial on essential is not
    assert crit.critical_gap(hard, "partial") is True
    assert crit.critical_gap(essential, "partial") is False
    # strength never critical; no match (None band) → never critical
    assert crit.critical_gap(hard, "strength") is False
    assert crit.critical_gap(hard, None) is False


def test_build_views_resolves_spans_and_flags_critical_gap() -> None:
    idx = _idx()
    val = {"assessments": [
        {"requirement": "Minimum 8 years", "explanation": "a hard bar",
         "hard_gate": True, "spans": ["sec-0"], "confidence": "high"},
    ]}
    parsed = crit.parse_criticality(("Minimum 8 years",), idx, val)
    items = crit.attach_criticality((_req("Minimum 8 years"),), parsed)
    match_json = '[{"criterion": "Minimum 8 years", "band": "gap", "evidence": ""}]'
    views = crit.build_requirement_views(items, _JD, match_json)
    v = views[0]
    assert v["criticality"] == "a hard bar"
    assert v["hard_gate"] is True
    assert v["coverage_band"] == "gap"
    assert v["critical_gap"] is True
    assert v["criticality_spans"][0]["id"] == "sec-0"
    assert v["criticality_spans"][0]["text"].startswith("Essential")


def test_build_views_without_a_match_leaves_criticality_standing_alone() -> None:
    items = (_req("Min 8 years"),)
    views = crit.build_requirement_views(items, _JD, None)   # no match result
    assert views[0]["coverage_band"] is None
    assert views[0]["critical_gap"] is False


def test_stale_stored_span_is_dropped_on_read() -> None:
    # a stored criticality references sec-5; if the JD no longer has it, the read drops it
    item = _req("X"); item["criticality"] = {"explanation": "e", "hard_gate": False, "spans": ["sec-5"], "confidence": "high"}
    views = crit.build_requirement_views((item,), "Only one short block.", None)
    assert views[0]["criticality_spans"] == []
