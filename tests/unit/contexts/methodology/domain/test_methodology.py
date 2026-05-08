"""Unit tests for the methodology aggregates (D74)."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from contexts.methodology.domain.methodology import (
    MethodologyRevision,
    MethodologyTemplate,
)


_TEMPLATE_ID = UUID("00000000-0000-4000-8000-000000000001")
_REVISION_ID = UUID("00000000-0000-4000-8000-000000000002")


def _template(**overrides) -> MethodologyTemplate:
    defaults = dict(
        id=_TEMPLATE_ID,
        name="LVT",
        description="Local-volume thinking baseline",
        created_by_user_id="alice",
        created_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return MethodologyTemplate(**defaults)


def _revision(**overrides) -> MethodologyRevision:
    defaults = dict(
        id=_REVISION_ID,
        methodology_template_id=_TEMPLATE_ID,
        version=1,
        system_prompt="You are a careful analyst.",
        source_ids=(),
        tool_allowlist=(),
        retrieval_strategy={"strategy": "vector_only", "params": {}},
        filter_tree={"node": {}},
        top_k=5,
        min_score=Decimal("0.7"),
        model_selection="qwen2.5:7b",
        created_by_user_id="alice",
        created_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
        previous_revision_hash="0" * 64,
        this_revision_hash="abc123",
    )
    defaults.update(overrides)
    return MethodologyRevision(**defaults)


def test_methodology_template_construction() -> None:
    template = _template()
    assert template.id == _TEMPLATE_ID
    assert template.name == "LVT"
    assert template.archived_at is None


def test_methodology_template_archived_at_optional() -> None:
    archived = datetime(2026, 6, 1, tzinfo=timezone.utc)
    template = _template(archived_at=archived)
    assert template.archived_at == archived


def test_methodology_template_is_frozen() -> None:
    template = _template()
    with pytest.raises(dataclasses.FrozenInstanceError):
        template.name = "renamed"  # type: ignore[misc]


def test_methodology_template_description_can_be_none() -> None:
    template = _template(description=None)
    assert template.description is None


def test_methodology_template_equality() -> None:
    t1 = _template()
    t2 = _template()
    assert t1 == t2


def test_methodology_revision_construction() -> None:
    rev = _revision()
    assert rev.version == 1
    assert rev.min_score == Decimal("0.7")
    assert rev.previous_revision_hash == "0" * 64


def test_methodology_revision_is_frozen() -> None:
    rev = _revision()
    with pytest.raises(dataclasses.FrozenInstanceError):
        rev.version = 2  # type: ignore[misc]


def test_methodology_revision_source_ids_are_tuple() -> None:
    src_a = UUID("00000000-0000-4000-8000-00000000a001")
    src_b = UUID("00000000-0000-4000-8000-00000000b002")
    rev = _revision(source_ids=(src_a, src_b))
    assert rev.source_ids == (src_a, src_b)
    # tuple is hashable; list would not be in a frozen dataclass field
    assert isinstance(rev.source_ids, tuple)


def test_methodology_revision_tool_allowlist_are_tuple() -> None:
    rev = _revision(tool_allowlist=("vector_search", "graph_traverse"))
    assert rev.tool_allowlist == ("vector_search", "graph_traverse")
    assert isinstance(rev.tool_allowlist, tuple)


def test_methodology_revision_jsonb_fields_are_mappings() -> None:
    rev = _revision(
        retrieval_strategy={"strategy": "hybrid", "params": {"alpha": 0.5}},
        filter_tree={"op": "and", "operands": []},
    )
    assert rev.retrieval_strategy["strategy"] == "hybrid"
    assert rev.filter_tree["op"] == "and"


def test_methodology_revision_chain_pointers_persisted() -> None:
    rev = _revision(
        previous_revision_hash="aa" * 32,
        this_revision_hash="bb" * 32,
    )
    assert rev.previous_revision_hash == "aa" * 32
    assert rev.this_revision_hash == "bb" * 32


def test_methodology_revision_decimal_min_score_preserved() -> None:
    rev = _revision(min_score=Decimal("0.95"))
    assert rev.min_score == Decimal("0.95")
    # Decimal type, not float
    assert isinstance(rev.min_score, Decimal)
