"""JD-extraction domain: the prompt, schema, and defensive parser — two context fields +
a list of discrete typed requirements (S103ad/D236, deepened S103ah/D240)."""

from __future__ import annotations

from contexts.daily_driver.domain.demand_requirements import IMPORTANCE_LEVELS
from contexts.daily_driver.domain.jd_extraction import (
    JD_CONTEXT_FIELD_KEYS,
    JD_EXTRACT_SCHEMA,
    MAX_JD_CHARS,
    ExtractedDemand,
    build_jd_extract_prompt,
    parse_jd_extract,
)


def test_schema_carries_context_fields_and_a_config_driven_requirements_array() -> None:
    assert JD_CONTEXT_FIELD_KEYS == ("role_open", "success_measures")
    props = JD_EXTRACT_SCHEMA["properties"]
    assert set(props) == {"role_open", "success_measures", "requirements"}
    assert JD_EXTRACT_SCHEMA["required"] == ["role_open", "success_measures", "requirements"]
    assert JD_EXTRACT_SCHEMA["additionalProperties"] is False
    # the requirements item schema is built config-driven from REQUIREMENT_FIELDS
    item = props["requirements"]["items"]
    assert set(item["properties"]) == {"text", "importance"}
    assert item["properties"]["importance"]["enum"] == list(IMPORTANCE_LEVELS)
    assert item["additionalProperties"] is False


def test_parse_yields_discrete_requirements_not_a_blob() -> None:
    # The compression fix: seven discrete essential items stay seven discrete items.
    e = parse_jd_extract({
        "role_open": "backfill after a departure",
        "success_measures": "ship the platform in 6 months",
        "requirements": [
            {"text": "Entrepreneurial mindset", "importance": "essential"},
            {"text": "Define, scale and execute strategy", "importance": "essential"},
            {"text": "Deep technical expertise", "importance": "essential"},
            {"text": "Stakeholder management", "importance": "essential"},
            {"text": "Team leadership", "importance": "essential"},
            {"text": "Delivery track record", "importance": "essential"},
            {"text": "Commercial acumen", "importance": "essential"},
            {"text": "Public-sector experience", "importance": "preferred"},
        ],
    })
    assert e.role_open == "backfill after a departure"
    assert e.success_measures == "ship the platform in 6 months"
    assert len(e.requirements) == 8  # nothing dropped, nothing merged
    texts = [r["text"] for r in e.requirements]
    assert "Entrepreneurial mindset" in texts
    assert "Define, scale and execute strategy" in texts
    # three-level importance captured from the JD's framing
    assert e.requirements[-1]["importance"] == "preferred"
    assert all(r["importance"] in IMPORTANCE_LEVELS for r in e.requirements)
    assert all(r["proof_state"] == "draft" for r in e.requirements)  # never a fact


def test_empty_context_fields_become_none_no_invention() -> None:
    e = parse_jd_extract({"role_open": "", "success_measures": "   ", "requirements": []})
    assert e.role_open is None
    assert e.success_measures is None
    assert e.requirements == ()


def test_missing_keys_and_non_dict_degrade_safely() -> None:
    assert parse_jd_extract({}) == ExtractedDemand(None, None, ())
    assert parse_jd_extract({"role_open": 42}) == ExtractedDemand(None, None, ())
    assert parse_jd_extract("not a dict") == ExtractedDemand(None, None, ())


def test_bad_requirement_entries_are_dropped_others_kept() -> None:
    e = parse_jd_extract({
        "role_open": "x", "success_measures": "y",
        "requirements": [
            {"text": "Real one", "importance": "essential"},
            {"text": "", "importance": "essential"},   # empty text dropped
            "not a dict",                                # dropped
            {"importance": "essential"},                 # no text dropped
            {"text": "Ungraded"},                        # importance defaults to essential
        ],
    })
    texts = [r["text"] for r in e.requirements]
    assert texts == ["Real one", "Ungraded"]
    assert e.requirements[1]["importance"] == "essential"


def test_context_drafts_returns_only_stated_fields() -> None:
    e = ExtractedDemand(role_open="a", success_measures=None, requirements=())
    assert e.context_drafts() == (("role_open", "a"),)
    assert ExtractedDemand(None, None, ()).context_drafts() == ()


def test_prompt_asks_for_discrete_requirements_and_caps_the_jd() -> None:
    prompt = build_jd_extract_prompt("x" * (MAX_JD_CHARS + 5000))
    assert "role_open" in prompt and "success_measures" in prompt
    # the anti-compression instruction + the three-level grading
    assert "One requirement per item" in prompt
    assert "seven items" in prompt  # nothing dropped, nothing merged
    for level in IMPORTANCE_LEVELS:
        assert level in prompt
    assert "EMPTY STRING" in prompt  # the no-invention instruction for context fields
    # the JD is capped so a huge paste cannot blow the context window
    assert ("x" * MAX_JD_CHARS) in prompt
    assert ("x" * (MAX_JD_CHARS + 1)) not in prompt
