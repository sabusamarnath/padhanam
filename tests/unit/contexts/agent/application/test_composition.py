"""Unit tests for compose_effective_constraint_bundle (D87 resolver, D88).

The resolver is load-bearing for every agent invocation: it turns a
role's static constraint bundle plus the methodology's per-role
overrides into the effective bundle the executor consumes. Tests
cover every (field, mode) admissibility per D87, the no-overrides
path (LVT case), the McKinsey ProblemFramer augment case, and the
shape-defence ``CompositionError`` cases.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from contexts.agent.application.composition import (
    CompositionError,
    compose_effective_constraint_bundle,
    SYSTEM_PROMPT_AUGMENT_SEPARATOR,
)
from contexts.agent.application.ports import RoleView
from shared_kernel import ToolAllowlistEntry


# Synthetic pinned tool entries used by the composition tests. The
# tool UUIDs are fixtures-only; the resolver doesn't look up the tool
# registry, it only operates on the (tool_id, revision_id) tuples
# composition produces.
_RETRIEVAL = ToolAllowlistEntry(
    tool_id=UUID("00000000-0000-0000-0000-000000000001"),
    revision_id=UUID("00000000-0000-0000-0000-000000000002"),
)
_SEARCH = ToolAllowlistEntry(
    tool_id=UUID("00000000-0000-0000-0000-000000000010"),
    revision_id=UUID("00000000-0000-0000-0000-000000000011"),
)
_WRITE_FILE = ToolAllowlistEntry(
    tool_id=UUID("00000000-0000-0000-0000-000000000020"),
    revision_id=UUID("00000000-0000-0000-0000-000000000021"),
)
_SUMMARISE = ToolAllowlistEntry(
    tool_id=UUID("00000000-0000-0000-0000-000000000030"),
    revision_id=UUID("00000000-0000-0000-0000-000000000031"),
)
_CALENDAR_SEND = ToolAllowlistEntry(
    tool_id=UUID("00000000-0000-0000-0000-000000000040"),
    revision_id=UUID("00000000-0000-0000-0000-000000000041"),
)


def _allowlist_dict(entry: ToolAllowlistEntry) -> dict[str, str]:
    return {"tool_id": str(entry.tool_id), "revision_id": str(entry.revision_id)}


def _lvt_role_view() -> RoleView:
    """A role view mirroring the LVTGuide role shape from S26a-1."""
    return RoleView(
        role_id=uuid4(),
        role_version=1,
        description="LVT guide.",
        system_prompt="You are an LVT coach.",
        tool_allowlist=(_RETRIEVAL,),
        retrieval_strategy={"primary": "vector"},
        filter_tree={},
        top_k=8,
        min_score=Decimal("0.5"),
        model_selection="qwen2.5:7b",
    )


def _mckinsey_problem_framer_view() -> RoleView:
    """A role view mirroring the McKinsey ProblemFramer role from S26b."""
    return RoleView(
        role_id=uuid4(),
        role_version=1,
        description="Frames problems for structured analysis.",
        system_prompt=(
            "You frame problems for structured analysis. Your job: receive "
            "a raw problem statement or topic from the user; produce a "
            "sharpened problem statement with explicit scope, context, "
            "complication, and success criteria."
        ),
        tool_allowlist=(_RETRIEVAL, _SEARCH),
        retrieval_strategy={"primary": "vector", "secondary": "graph"},
        filter_tree={},
        top_k=8,
        min_score=Decimal("0.5"),
        model_selection="qwen2.5:7b",
    )


# 1. Empty-overrides path (LVT case).

def test_no_overrides_returns_role_base_unchanged() -> None:
    role = _lvt_role_view()
    result = compose_effective_constraint_bundle(
        role=role,
        methodology_overrides={},
    )
    assert result.system_prompt == role.system_prompt
    assert result.tool_allowlist == role.tool_allowlist
    assert result.retrieval_strategy == role.retrieval_strategy
    assert result.filter_tree == role.filter_tree
    assert result.top_k == role.top_k
    assert result.min_score == role.min_score
    assert result.model_selection == role.model_selection


# 2. system_prompt: augment (McKinsey case) and replace.

def test_system_prompt_augment_concatenates_with_two_newlines() -> None:
    """The McKinsey ProblemFramer case: methodology adds SCQ framework
    instructions to the role's function-focused base prompt."""
    role = _mckinsey_problem_framer_view()
    overrides = {
        "system_prompt": {
            "mode": "augment",
            "value": "Apply the SCQ framework (Situation, Complication, Question) when framing.",
        },
    }
    result = compose_effective_constraint_bundle(
        role=role,
        methodology_overrides=overrides,
    )
    assert result.system_prompt == (
        role.system_prompt
        + SYSTEM_PROMPT_AUGMENT_SEPARATOR
        + "Apply the SCQ framework (Situation, Complication, Question) when framing."
    )
    # Sanity: the base prompt is preserved verbatim and the override
    # appears as a separate paragraph.
    assert role.system_prompt in result.system_prompt
    assert "SCQ framework" in result.system_prompt


def test_system_prompt_replace_substitutes() -> None:
    role = _lvt_role_view()
    overrides = {
        "system_prompt": {"mode": "replace", "value": "You are a calibration coach."},
    }
    result = compose_effective_constraint_bundle(
        role=role,
        methodology_overrides=overrides,
    )
    assert result.system_prompt == "You are a calibration coach."


# 3. tool_allowlist: tighten and replace.

def test_tool_allowlist_tighten_intersects_preserving_role_order() -> None:
    role = _mckinsey_problem_framer_view()
    # role.tool_allowlist == (_RETRIEVAL, _SEARCH); the override lists
    # _SEARCH and _WRITE_FILE by their pinned tuples. The intersection
    # by tool_id keeps _SEARCH (also in role) and drops _RETRIEVAL
    # (not in override) and _WRITE_FILE (not in role).
    overrides = {
        "tool_allowlist": {
            "mode": "tighten",
            "value": [_allowlist_dict(_SEARCH), _allowlist_dict(_WRITE_FILE)],
        },
    }
    result = compose_effective_constraint_bundle(
        role=role,
        methodology_overrides=overrides,
    )
    assert result.tool_allowlist == (_SEARCH,)


def test_tool_allowlist_tighten_empty_intersection_yields_empty_tuple() -> None:
    role = _lvt_role_view()
    overrides = {
        "tool_allowlist": {
            "mode": "tighten",
            "value": [_allowlist_dict(_CALENDAR_SEND)],
        },
    }
    result = compose_effective_constraint_bundle(
        role=role,
        methodology_overrides=overrides,
    )
    assert result.tool_allowlist == ()


def test_tool_allowlist_replace_substitutes() -> None:
    role = _lvt_role_view()
    overrides = {
        "tool_allowlist": {
            "mode": "replace",
            "value": [_allowlist_dict(_SEARCH), _allowlist_dict(_SUMMARISE)],
        },
    }
    result = compose_effective_constraint_bundle(
        role=role,
        methodology_overrides=overrides,
    )
    assert result.tool_allowlist == (_SEARCH, _SUMMARISE)


# 4. retrieval_strategy: replace only.

def test_retrieval_strategy_replace_substitutes() -> None:
    role = _lvt_role_view()
    overrides = {
        "retrieval_strategy": {
            "mode": "replace",
            "value": {"primary": "graph", "secondary": "vector"},
        },
    }
    result = compose_effective_constraint_bundle(
        role=role,
        methodology_overrides=overrides,
    )
    assert result.retrieval_strategy == {"primary": "graph", "secondary": "vector"}


# 5. filter_tree: tighten (AND-merge) and replace.

def test_filter_tree_tighten_with_empty_base_uses_override() -> None:
    role = _lvt_role_view()  # empty filter_tree
    overrides = {
        "filter_tree": {
            "mode": "tighten",
            "value": {"op": "eq", "field": "source_type", "value": "transcript"},
        },
    }
    result = compose_effective_constraint_bundle(
        role=role,
        methodology_overrides=overrides,
    )
    assert result.filter_tree == {
        "op": "eq",
        "field": "source_type",
        "value": "transcript",
    }


def test_filter_tree_tighten_with_both_non_empty_and_merges() -> None:
    role = _lvt_role_view()
    role_with_filter = RoleView(
        role_id=role.role_id,
        role_version=role.role_version,
        description=role.description,
        system_prompt=role.system_prompt,
        tool_allowlist=role.tool_allowlist,
        retrieval_strategy=role.retrieval_strategy,
        filter_tree={"op": "eq", "field": "department", "value": "engineering"},
        top_k=role.top_k,
        min_score=role.min_score,
        model_selection=role.model_selection,
    )
    overrides = {
        "filter_tree": {
            "mode": "tighten",
            "value": {"op": "gt", "field": "year", "value": 2024},
        },
    }
    result = compose_effective_constraint_bundle(
        role=role_with_filter,
        methodology_overrides=overrides,
    )
    assert result.filter_tree == {
        "op": "and",
        "operands": [
            {"op": "eq", "field": "department", "value": "engineering"},
            {"op": "gt", "field": "year", "value": 2024},
        ],
    }


def test_filter_tree_replace_substitutes() -> None:
    role = _lvt_role_view()
    overrides = {
        "filter_tree": {
            "mode": "replace",
            "value": {"op": "eq", "field": "tag", "value": "primary"},
        },
    }
    result = compose_effective_constraint_bundle(
        role=role,
        methodology_overrides=overrides,
    )
    assert result.filter_tree == {"op": "eq", "field": "tag", "value": "primary"}


# 6. top_k: tighten (cap) and replace.

def test_top_k_tighten_takes_lower_value() -> None:
    role = _lvt_role_view()  # top_k = 8
    overrides = {"top_k": {"mode": "tighten", "value": 3}}
    result = compose_effective_constraint_bundle(
        role=role,
        methodology_overrides=overrides,
    )
    assert result.top_k == 3


def test_top_k_tighten_with_larger_override_keeps_role_base() -> None:
    """Methodology may only decrease top_k; an override that would
    raise the cap is silently dominated by the role base."""
    role = _lvt_role_view()  # top_k = 8
    overrides = {"top_k": {"mode": "tighten", "value": 20}}
    result = compose_effective_constraint_bundle(
        role=role,
        methodology_overrides=overrides,
    )
    assert result.top_k == 8


def test_top_k_replace_substitutes() -> None:
    role = _lvt_role_view()
    overrides = {"top_k": {"mode": "replace", "value": 25}}
    result = compose_effective_constraint_bundle(
        role=role,
        methodology_overrides=overrides,
    )
    assert result.top_k == 25


# 7. min_score: tighten (floor) and replace.

def test_min_score_tighten_takes_higher_value() -> None:
    role = _lvt_role_view()  # min_score = 0.5
    overrides = {"min_score": {"mode": "tighten", "value": "0.75"}}
    result = compose_effective_constraint_bundle(
        role=role,
        methodology_overrides=overrides,
    )
    assert result.min_score == Decimal("0.75")


def test_min_score_tighten_with_lower_override_keeps_role_base() -> None:
    role = _lvt_role_view()  # min_score = 0.5
    overrides = {"min_score": {"mode": "tighten", "value": "0.2"}}
    result = compose_effective_constraint_bundle(
        role=role,
        methodology_overrides=overrides,
    )
    assert result.min_score == Decimal("0.5")


def test_min_score_replace_substitutes() -> None:
    role = _lvt_role_view()
    overrides = {"min_score": {"mode": "replace", "value": Decimal("0.1")}}
    result = compose_effective_constraint_bundle(
        role=role,
        methodology_overrides=overrides,
    )
    assert result.min_score == Decimal("0.1")


# 8. model_selection: replace only.

def test_model_selection_replace_substitutes() -> None:
    role = _lvt_role_view()
    overrides = {"model_selection": {"mode": "replace", "value": "gpt-4o-mini"}}
    result = compose_effective_constraint_bundle(
        role=role,
        methodology_overrides=overrides,
    )
    assert result.model_selection == "gpt-4o-mini"


# 9. Shape defence — CompositionError on malformed entries.

def test_malformed_entry_missing_value_raises() -> None:
    role = _lvt_role_view()
    overrides = {"system_prompt": {"mode": "augment"}}
    with pytest.raises(CompositionError, match="malformed"):
        compose_effective_constraint_bundle(
            role=role,
            methodology_overrides=overrides,
        )


def test_malformed_entry_missing_mode_raises() -> None:
    role = _lvt_role_view()
    overrides = {"system_prompt": {"value": "x"}}
    with pytest.raises(CompositionError, match="malformed"):
        compose_effective_constraint_bundle(
            role=role,
            methodology_overrides=overrides,
        )


def test_unknown_mode_for_field_raises() -> None:
    """The substrate validates writes per D87 so this case requires a
    substrate bypass; the resolver still defends explicitly."""
    role = _lvt_role_view()
    overrides = {"system_prompt": {"mode": "tighten", "value": "x"}}
    with pytest.raises(CompositionError, match="unexpected"):
        compose_effective_constraint_bundle(
            role=role,
            methodology_overrides=overrides,
        )
