"""Unit tests for the agent aggregates (D75)."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from contexts.agent.domain.agent import AgentRevision, AgentTemplate


_TEMPLATE_ID = UUID("00000000-0000-4000-8000-000000000001")
_REVISION_ID = UUID("00000000-0000-4000-8000-000000000002")
_METHODOLOGY_TEMPLATE_ID = UUID("00000000-0000-4000-8000-0000000000aa")
_ROLE_TEMPLATE_ID = UUID("00000000-0000-4000-8000-0000000000bb")


def _template(**overrides) -> AgentTemplate:
    defaults = dict(
        id=_TEMPLATE_ID,
        name="lvt-pm-agent",
        description="LVT-derived product-manager agent",
        created_by_user_id="alice",
        created_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return AgentTemplate(**defaults)


def _revision(**overrides) -> AgentRevision:
    defaults = dict(
        id=_REVISION_ID,
        agent_template_id=_TEMPLATE_ID,
        version=1,
        system_prompt="You are a careful PM.",
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
    return AgentRevision(**defaults)


# ---------------------------------------------------------------------
# AgentTemplate
# ---------------------------------------------------------------------


def test_agent_template_construction_blank() -> None:
    template = _template()
    assert template.id == _TEMPLATE_ID
    assert template.name == "lvt-pm-agent"
    assert template.source_methodology_template_id is None
    assert template.source_methodology_template_version is None
    assert template.source_role_id is None
    assert template.source_role_version is None
    assert template.archived_at is None


def test_agent_template_construction_clone_from_methodology() -> None:
    template = _template(
        source_methodology_template_id=_METHODOLOGY_TEMPLATE_ID,
        source_methodology_template_version=1,
        source_role_id=_ROLE_TEMPLATE_ID,
        source_role_version=1,
    )
    assert template.source_methodology_template_id == _METHODOLOGY_TEMPLATE_ID
    assert template.source_methodology_template_version == 1
    assert template.source_role_id == _ROLE_TEMPLATE_ID
    assert template.source_role_version == 1


def test_agent_template_construction_clone_from_role_only() -> None:
    """D86 role-cloned agent: role pair populated, methodology NULL."""
    template = _template(
        source_role_id=_ROLE_TEMPLATE_ID,
        source_role_version=2,
    )
    assert template.source_methodology_template_id is None
    assert template.source_methodology_template_version is None
    assert template.source_role_id == _ROLE_TEMPLATE_ID
    assert template.source_role_version == 2


def test_agent_template_is_frozen() -> None:
    template = _template()
    with pytest.raises(dataclasses.FrozenInstanceError):
        template.name = "changed"  # type: ignore[misc]


def test_agent_template_methodology_paired_null_id_only_raises() -> None:
    with pytest.raises(ValueError, match="paired-NULL invariant"):
        _template(
            source_methodology_template_id=_METHODOLOGY_TEMPLATE_ID,
            source_methodology_template_version=None,
        )


def test_agent_template_methodology_paired_null_version_only_raises() -> None:
    with pytest.raises(ValueError, match="paired-NULL invariant"):
        _template(
            source_methodology_template_id=None,
            source_methodology_template_version=2,
        )


def test_agent_template_role_paired_null_id_only_raises() -> None:
    """D86 role-lineage paired-NULL invariant, independent of methodology."""
    with pytest.raises(ValueError, match="role lineage.*paired-NULL"):
        _template(
            source_role_id=_ROLE_TEMPLATE_ID,
            source_role_version=None,
        )


def test_agent_template_role_paired_null_version_only_raises() -> None:
    with pytest.raises(ValueError, match="role lineage.*paired-NULL"):
        _template(
            source_role_id=None,
            source_role_version=3,
        )


def test_agent_template_archived_template() -> None:
    archived_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
    template = _template(archived_at=archived_at)
    assert template.archived_at == archived_at


def test_agent_template_value_equality() -> None:
    a = _template()
    b = _template()
    assert a == b


# ---------------------------------------------------------------------
# AgentRevision
# ---------------------------------------------------------------------


def test_agent_revision_construction() -> None:
    revision = _revision()
    assert revision.id == _REVISION_ID
    assert revision.version == 1
    assert revision.previous_revision_hash == "0" * 64
    assert revision.this_revision_hash == "abc123"


def test_agent_revision_is_frozen() -> None:
    revision = _revision()
    with pytest.raises(dataclasses.FrozenInstanceError):
        revision.version = 2  # type: ignore[misc]


def test_agent_revision_no_name_or_description_field() -> None:
    """D75 chain-self-containment: name and description are read from
    the parent template at hash-compute time and are not persisted on
    the revision row. The dataclass must not carry these fields."""
    field_names = {f.name for f in dataclasses.fields(AgentRevision)}
    assert "name" not in field_names
    assert "description" not in field_names


def test_agent_revision_carries_genesis_previous_hash_for_revision_one() -> None:
    revision = _revision(version=1, previous_revision_hash="0" * 64)
    assert revision.previous_revision_hash == "0" * 64


def test_agent_revision_chain_pointer_carries_predecessor_hash() -> None:
    rev2 = _revision(version=2, previous_revision_hash="abc123", this_revision_hash="def456")
    assert rev2.previous_revision_hash == "abc123"
    assert rev2.this_revision_hash == "def456"


def test_agent_revision_value_equality() -> None:
    a = _revision()
    b = _revision()
    assert a == b
