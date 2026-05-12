"""Unit tests for the methodology aggregates (D74, refactored S26a-1 per D86)."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from uuid import UUID

import pytest

from contexts.methodology.domain.methodology import (
    MethodologyRevision,
    MethodologyTemplate,
    RoleRef,
)


_TEMPLATE_ID = UUID("00000000-0000-4000-8000-000000000001")
_REVISION_ID = UUID("00000000-0000-4000-8000-000000000002")
_ROLE_ID = UUID("00000000-0000-4000-8000-0000000c0001")


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


def _role_ref(**overrides) -> RoleRef:
    defaults: dict[str, object] = dict(
        role_id=_ROLE_ID,
        role_version=1,
    )
    defaults.update(overrides)
    return RoleRef(**defaults)


def _revision(**overrides) -> MethodologyRevision:
    defaults = dict(
        id=_REVISION_ID,
        methodology_template_id=_TEMPLATE_ID,
        version=1,
        role_refs=(_role_ref(),),
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


def test_role_ref_construction() -> None:
    ref = _role_ref()
    assert ref.role_id == _ROLE_ID
    assert ref.role_version == 1
    # D87: overrides defaults to an empty dict (the trivial no-op case),
    # not None. Empty maps to ``null`` only at the canonical-JSON
    # boundary for byte-stability with pre-D87 LVT hashes.
    assert ref.overrides == {}


def test_role_ref_is_frozen() -> None:
    ref = _role_ref()
    with pytest.raises(dataclasses.FrozenInstanceError):
        ref.role_version = 2  # type: ignore[misc]


def test_role_ref_overrides_carries_structured_payload() -> None:
    """D87: overrides is dict[str, dict[str, Any]] keyed by role field."""
    payload = {"system_prompt": {"mode": "augment", "value": "specialise"}}
    ref = _role_ref(overrides=payload)
    assert ref.overrides == payload


def test_methodology_revision_construction() -> None:
    rev = _revision()
    assert rev.version == 1
    assert rev.previous_revision_hash == "0" * 64
    assert len(rev.role_refs) == 1
    assert rev.role_refs[0].role_id == _ROLE_ID


def test_methodology_revision_is_frozen() -> None:
    rev = _revision()
    with pytest.raises(dataclasses.FrozenInstanceError):
        rev.version = 2  # type: ignore[misc]


def test_methodology_revision_role_refs_tuple() -> None:
    second = _role_ref(
        role_id=UUID("00000000-0000-4000-8000-0000000c0002"),
        role_version=3,
    )
    rev = _revision(role_refs=(_role_ref(), second))
    assert isinstance(rev.role_refs, tuple)
    assert len(rev.role_refs) == 2
    assert rev.role_refs[1].role_version == 3


def test_methodology_revision_chain_pointers_persisted() -> None:
    rev = _revision(
        previous_revision_hash="aa" * 32,
        this_revision_hash="bb" * 32,
    )
    assert rev.previous_revision_hash == "aa" * 32
    assert rev.this_revision_hash == "bb" * 32
