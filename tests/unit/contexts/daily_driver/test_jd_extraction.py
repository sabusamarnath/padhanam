"""JD-extraction domain: the prompt, schema, and defensive parser (S103ad, D236)."""

from __future__ import annotations

from contexts.daily_driver.domain.jd_extraction import (
    JD_DRAFT_FIELD_KEYS,
    JD_EXTRACT_SCHEMA,
    MAX_JD_CHARS,
    ExtractedQualification,
    build_jd_extract_prompt,
    parse_jd_extract,
)


def test_the_three_fields_and_the_schema() -> None:
    assert JD_DRAFT_FIELD_KEYS == ("role_open", "success_measures", "selection_criteria")
    assert set(JD_EXTRACT_SCHEMA["properties"]) == set(JD_DRAFT_FIELD_KEYS)
    assert JD_EXTRACT_SCHEMA["required"] == list(JD_DRAFT_FIELD_KEYS)
    assert JD_EXTRACT_SCHEMA["additionalProperties"] is False


def test_parse_full_extract() -> None:
    e = parse_jd_extract({
        "role_open": "backfill after a departure",
        "success_measures": "ship the platform in 6 months",
        "selection_criteria": "8y backend, Python, distributed systems",
    })
    assert e.role_open == "backfill after a departure"
    assert e.success_measures == "ship the platform in 6 months"
    assert e.selection_criteria == "8y backend, Python, distributed systems"


def test_empty_string_and_whitespace_become_none_no_invention() -> None:
    # The prompt tells the model to return "" for a field the JD does not state;
    # an empty/whitespace field is NO draft (None), so nothing is written for it.
    e = parse_jd_extract({"role_open": "", "success_measures": "   ", "selection_criteria": "x"})
    assert e.role_open is None
    assert e.success_measures is None
    assert e.selection_criteria == "x"


def test_missing_keys_and_non_dict_degrade_to_none() -> None:
    assert parse_jd_extract({}) == ExtractedQualification(None, None, None)
    assert parse_jd_extract({"role_open": 42}) == ExtractedQualification(None, None, None)
    assert parse_jd_extract("not a dict") == ExtractedQualification(None, None, None)


def test_drafts_returns_only_non_empty_fields() -> None:
    e = ExtractedQualification(role_open="a", success_measures=None, selection_criteria="c")
    assert e.drafts() == (("role_open", "a"), ("selection_criteria", "c"))
    assert ExtractedQualification(None, None, None).drafts() == ()


def test_prompt_names_the_fields_and_caps_the_jd() -> None:
    prompt = build_jd_extract_prompt("x" * (MAX_JD_CHARS + 5000))
    assert "role_open" in prompt and "success_measures" in prompt and "selection_criteria" in prompt
    assert "EMPTY STRING" in prompt  # the no-invention instruction
    # the JD is capped so a huge paste cannot blow the context window
    assert ("x" * MAX_JD_CHARS) in prompt
    assert ("x" * (MAX_JD_CHARS + 1)) not in prompt
