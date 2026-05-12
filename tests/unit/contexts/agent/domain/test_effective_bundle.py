"""Unit tests for EffectiveConstraintBundle (D88).

The bundle is the output of the composition resolver and the central
shape carried through the invocation surface. These tests pin its
frozen-dataclass invariants and the field types so future composition
work has a stable target.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from contexts.agent.domain.effective_bundle import EffectiveConstraintBundle


def _sample_bundle() -> EffectiveConstraintBundle:
    return EffectiveConstraintBundle(
        system_prompt="You are a problem framer.\n\nApply the SCQ framework.",
        tool_allowlist=("retrieval",),
        retrieval_strategy={"primary": "vector"},
        filter_tree={},
        top_k=8,
        min_score=Decimal("0.5"),
        model_selection="qwen2.5:7b",
    )


def test_bundle_construction_carries_all_fields() -> None:
    b = _sample_bundle()
    assert b.system_prompt.startswith("You are a problem framer.")
    assert "Apply the SCQ framework." in b.system_prompt
    assert b.tool_allowlist == ("retrieval",)
    assert b.retrieval_strategy == {"primary": "vector"}
    assert b.filter_tree == {}
    assert b.top_k == 8
    assert b.min_score == Decimal("0.5")
    assert b.model_selection == "qwen2.5:7b"


def test_bundle_is_frozen() -> None:
    b = _sample_bundle()
    with pytest.raises(FrozenInstanceError):
        b.system_prompt = "different"  # type: ignore[misc]


def test_bundle_equality_by_value() -> None:
    a = _sample_bundle()
    b = _sample_bundle()
    assert a == b
    assert a is not b
