"""CV-extraction domain: the prompt, schema, defensive parser, deterministic ids
(S103af, D238)."""

from __future__ import annotations

from contexts.daily_driver.domain.cv_extraction import (
    CV_EXTRACT_SCHEMA,
    MAX_CV_CHARS,
    MAX_EXPERIENCES,
    MAX_SKILLS,
    ExtractedProfile,
    build_cv_extract_prompt,
    normalize_item,
    parse_cv_extract,
    skill_item_id,
)


def test_schema_is_two_string_lists() -> None:
    assert set(CV_EXTRACT_SCHEMA["properties"]) == {"skills", "experiences"}
    assert CV_EXTRACT_SCHEMA["required"] == ["skills", "experiences"]
    assert CV_EXTRACT_SCHEMA["additionalProperties"] is False
    for k in ("skills", "experiences"):
        assert CV_EXTRACT_SCHEMA["properties"][k]["type"] == "array"
        assert CV_EXTRACT_SCHEMA["properties"][k]["items"]["type"] == "string"


def test_parse_full_extract_items_skills_then_experiences() -> None:
    p = parse_cv_extract({
        "skills": ["Product strategy", "SQL"],
        "experiences": ["Led a 12-person org"],
    })
    assert p.skills == ("Product strategy", "SQL")
    assert p.experiences == ("Led a 12-person org",)
    assert p.items() == (
        ("skill", "Product strategy"),
        ("skill", "SQL"),
        ("experience", "Led a 12-person org"),
    )


def test_parse_dedups_case_insensitive_and_collapses_whitespace() -> None:
    p = parse_cv_extract({
        "skills": ["Product  strategy", "product strategy", "  PRODUCT STRATEGY ", "SQL", ""],
        "experiences": [],
    })
    # one 'product strategy' survives (whitespace-collapsed to the first form), plus SQL
    assert p.skills == ("Product strategy", "SQL")


def test_parse_caps_the_lists() -> None:
    p = parse_cv_extract({
        "skills": [f"skill {i}" for i in range(MAX_SKILLS + 20)],
        "experiences": [f"exp {i}" for i in range(MAX_EXPERIENCES + 20)],
    })
    assert len(p.skills) == MAX_SKILLS
    assert len(p.experiences) == MAX_EXPERIENCES


def test_parse_non_dict_and_missing_keys_degrade_to_empty() -> None:
    assert parse_cv_extract("nope") == ExtractedProfile((), ())
    assert parse_cv_extract({}) == ExtractedProfile((), ())
    # a non-list value, and non-string members, are dropped defensively
    assert parse_cv_extract({"skills": 42, "experiences": [1, "ok", None]}) == \
        ExtractedProfile((), ("ok",))


def test_skill_item_id_is_deterministic_and_discriminating() -> None:
    # stable across casing + whitespace (same normalized key -> same id)
    assert skill_item_id("skill", "Product strategy") == skill_item_id("skill", "  product   STRATEGY ")
    # distinct text -> distinct id; kind participates in the key
    assert skill_item_id("skill", "SQL") != skill_item_id("skill", "Python")
    assert skill_item_id("skill", "SQL") != skill_item_id("experience", "SQL")


def test_normalize_item() -> None:
    assert normalize_item("  Product   Strategy ") == "product strategy"
    assert normalize_item(None) == ""


def test_prompt_names_both_lists_forbids_invention_and_caps_the_cv() -> None:
    prompt = build_cv_extract_prompt("y" * (MAX_CV_CHARS + 5000))
    assert "skills:" in prompt and "experiences:" in prompt
    assert "invent" in prompt.lower()  # the no-invention instruction
    assert ("y" * MAX_CV_CHARS) in prompt
    assert ("y" * (MAX_CV_CHARS + 1)) not in prompt
