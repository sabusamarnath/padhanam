"""Unit tests for D87's override-mode space and authoring projection.

Covers ``contexts/methodology/domain/overrides.py``: the default-mode
table, admissible-mode validation, and the projection from authoring-
shape (flat or structured) to the canonical structured form D87
commits the substrate to.
"""

from __future__ import annotations

import pytest

from contexts.methodology.domain.overrides import (
    ALL_MODES,
    DEFAULT_MODE_BY_FIELD,
    MODE_AUGMENT,
    MODE_REPLACE,
    MODE_TIGHTEN,
    OverrideValidationError,
    project_overrides,
    validate_override,
)


def test_default_mode_table_covers_full_role_bundle() -> None:
    assert set(DEFAULT_MODE_BY_FIELD) == {
        "system_prompt",
        "tool_allowlist",
        "source_filter",
        "retrieval_strategy",
        "filter_tree",
        "top_k",
        "min_score",
        "model_selection",
        "cost_ceiling",
    }


def test_default_mode_per_field_matches_d87() -> None:
    assert DEFAULT_MODE_BY_FIELD["system_prompt"] == MODE_AUGMENT
    assert DEFAULT_MODE_BY_FIELD["tool_allowlist"] == MODE_TIGHTEN
    assert DEFAULT_MODE_BY_FIELD["source_filter"] == MODE_TIGHTEN
    assert DEFAULT_MODE_BY_FIELD["retrieval_strategy"] == MODE_REPLACE
    assert DEFAULT_MODE_BY_FIELD["filter_tree"] == MODE_TIGHTEN
    assert DEFAULT_MODE_BY_FIELD["top_k"] == MODE_TIGHTEN
    assert DEFAULT_MODE_BY_FIELD["min_score"] == MODE_TIGHTEN
    assert DEFAULT_MODE_BY_FIELD["model_selection"] == MODE_REPLACE
    assert DEFAULT_MODE_BY_FIELD["cost_ceiling"] == MODE_TIGHTEN


def test_all_modes_constant_matches_d87() -> None:
    assert ALL_MODES == {MODE_AUGMENT, MODE_REPLACE, MODE_TIGHTEN}


@pytest.mark.parametrize(
    "field,mode",
    [
        ("system_prompt", MODE_AUGMENT),
        ("system_prompt", MODE_REPLACE),
        ("tool_allowlist", MODE_TIGHTEN),
        ("tool_allowlist", MODE_REPLACE),
        ("source_filter", MODE_TIGHTEN),
        ("source_filter", MODE_REPLACE),
        ("retrieval_strategy", MODE_REPLACE),
        ("filter_tree", MODE_TIGHTEN),
        ("filter_tree", MODE_REPLACE),
        ("top_k", MODE_TIGHTEN),
        ("top_k", MODE_REPLACE),
        ("min_score", MODE_TIGHTEN),
        ("min_score", MODE_REPLACE),
        ("model_selection", MODE_REPLACE),
        ("cost_ceiling", MODE_TIGHTEN),
        ("cost_ceiling", MODE_REPLACE),
    ],
)
def test_validate_override_admits_admissible_pairs(
    field: str, mode: str
) -> None:
    validate_override(field, mode)  # no raise


@pytest.mark.parametrize(
    "field,mode",
    [
        ("system_prompt", MODE_TIGHTEN),  # soft free-text rejects tighten
        ("tool_allowlist", MODE_AUGMENT),  # hard rejects augment
        ("retrieval_strategy", MODE_AUGMENT),  # soft non-text rejects augment
        ("retrieval_strategy", MODE_TIGHTEN),  # soft non-text rejects tighten
        ("model_selection", MODE_AUGMENT),
        ("model_selection", MODE_TIGHTEN),
        ("top_k", MODE_AUGMENT),
        ("filter_tree", MODE_AUGMENT),
    ],
)
def test_validate_override_rejects_inadmissible_pairs(
    field: str, mode: str
) -> None:
    with pytest.raises(OverrideValidationError):
        validate_override(field, mode)


def test_validate_override_rejects_unknown_mode() -> None:
    with pytest.raises(OverrideValidationError, match="unknown override mode"):
        validate_override("system_prompt", "merge")


def test_validate_override_rejects_unknown_field() -> None:
    with pytest.raises(
        OverrideValidationError, match="not part of the role constraint bundle"
    ):
        validate_override("not_a_field", MODE_REPLACE)


# ---------------------------------------------------------------------
# Projection: flat → structured
# ---------------------------------------------------------------------


def test_project_overrides_returns_empty_dict_for_none_input() -> None:
    assert project_overrides(None) == {}


def test_project_overrides_returns_empty_dict_for_empty_input() -> None:
    assert project_overrides({}) == {}


def test_project_overrides_expands_flat_values_using_default_mode() -> None:
    raw = {
        "system_prompt": "you frame problems",
        "retrieval_strategy": {"strategy": "vector_only", "params": {}},
        "top_k": 12,
    }
    out = project_overrides(raw)
    assert out == {
        "system_prompt": {"mode": MODE_AUGMENT, "value": "you frame problems"},
        "retrieval_strategy": {
            "mode": MODE_REPLACE,
            "value": {"strategy": "vector_only", "params": {}},
        },
        "top_k": {"mode": MODE_TIGHTEN, "value": 12},
    }


def test_project_overrides_passes_structured_values_through() -> None:
    raw = {
        "system_prompt": {
            "mode": MODE_REPLACE,
            "value": "you replace the base prompt entirely",
        },
        "tool_allowlist": {
            "mode": MODE_REPLACE,
            "value": ["search_v2", "draft_v1"],
        },
    }
    out = project_overrides(raw)
    assert out == raw


def test_project_overrides_drops_none_values() -> None:
    raw = {
        "system_prompt": "augment me",
        "tool_allowlist": None,
    }
    out = project_overrides(raw)
    assert "tool_allowlist" not in out
    assert out["system_prompt"] == {
        "mode": MODE_AUGMENT,
        "value": "augment me",
    }


def test_project_overrides_raises_on_unknown_field_flat() -> None:
    with pytest.raises(
        OverrideValidationError, match="not part of the role constraint bundle"
    ):
        project_overrides({"unknown_field": "value"})


def test_project_overrides_raises_on_unknown_field_structured() -> None:
    with pytest.raises(
        OverrideValidationError, match="not part of the role constraint bundle"
    ):
        project_overrides(
            {"unknown_field": {"mode": MODE_REPLACE, "value": "v"}}
        )


def test_project_overrides_raises_on_inadmissible_pair_in_structured() -> None:
    with pytest.raises(
        OverrideValidationError, match="inadmissible for field"
    ):
        project_overrides(
            {"system_prompt": {"mode": MODE_TIGHTEN, "value": "x"}}
        )


def test_project_overrides_raises_on_unknown_mode_in_structured() -> None:
    with pytest.raises(OverrideValidationError, match="unknown override mode"):
        project_overrides(
            {"system_prompt": {"mode": "fold", "value": "x"}}
        )


def test_project_overrides_treats_dict_value_with_extra_keys_as_flat() -> None:
    """A non-structured dict (extra keys beyond mode/value, or missing one)
    is treated as a flat value and projected via the default mode."""
    raw = {
        "filter_tree": {"node": {"and": []}, "extras": "ignored"},
    }
    out = project_overrides(raw)
    assert out["filter_tree"] == {
        "mode": MODE_TIGHTEN,
        "value": {"node": {"and": []}, "extras": "ignored"},
    }
