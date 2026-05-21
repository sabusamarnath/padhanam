"""Unit tests for DataPoint and its Revisable Protocol conformance (D124, D125)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from contexts.portfolio.domain import (
    Assertion,
    AssertionType,
    DataPoint,
    DataPointType,
)
from shared_kernel import ActorReference, AssertionChange, Revisable

_ACTOR = ActorReference(user_id="operator")


def _initial_assertion(data_point_id: UUID, tenant_id: UUID) -> Assertion:
    return Assertion(
        id=uuid4(),
        data_point_id=data_point_id,
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        assertion_type=AssertionType.INITIAL,
        revises_assertion_id=None,
        value={"progress": 0},
        authored_by=_ACTOR,
        created_at=datetime.now(timezone.utc),
    )


def _data_point(**overrides: Any) -> DataPoint:
    dp_id: UUID = overrides.pop("id", uuid4())
    tenant_id: UUID = overrides.get("tenant_id", uuid4())
    base: dict[str, Any] = dict(
        id=dp_id,
        case_id=uuid4(),
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        data_point_type=DataPointType.GOAL,
        value={"progress": 0},
        authored_by=_ACTOR,
        created_at=datetime.now(timezone.utc),
        assertions=(_initial_assertion(dp_id, tenant_id),),
    )
    base.update(overrides)
    return DataPoint(**base)


def test_construction_happy_path() -> None:
    dp = _data_point()
    assert dp.data_point_type is DataPointType.GOAL
    assert len(dp.assertions) == 1
    assert dp.certainty is None


def test_is_frozen() -> None:
    dp = _data_point()
    with pytest.raises(FrozenInstanceError):
        dp.value = {}  # type: ignore[misc]


def test_empty_jurisdiction_rejected() -> None:
    with pytest.raises(ValueError, match="jurisdiction"):
        _data_point(jurisdiction="")


def test_certainty_out_of_range_rejected() -> None:
    with pytest.raises(ValueError, match="certainty"):
        _data_point(certainty=1.5)


def test_certainty_none_ok() -> None:
    assert _data_point(certainty=None).certainty is None


def test_certainty_in_range_ok() -> None:
    assert _data_point(certainty=0.5).certainty == 0.5


def test_empty_assertions_rejected() -> None:
    with pytest.raises(ValueError, match="INITIAL"):
        _data_point(assertions=())


def test_first_assertion_must_be_initial() -> None:
    dp_id, tenant_id = uuid4(), uuid4()
    rev = Assertion(
        id=uuid4(),
        data_point_id=dp_id,
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        assertion_type=AssertionType.REVISION,
        revises_assertion_id=uuid4(),
        value={},
        authored_by=_ACTOR,
        created_at=datetime.now(timezone.utc),
    )
    with pytest.raises(ValueError, match="first assertion"):
        _data_point(id=dp_id, tenant_id=tenant_id, assertions=(rev,))


def test_current_value_is_latest() -> None:
    dp = _data_point()
    revised = dp.revise(AssertionChange(value={"progress": 50}), _ACTOR)
    assert revised.current_value == {"progress": 50}


def test_revise_appends_chained_revision() -> None:
    dp = _data_point()
    revised = dp.revise(AssertionChange(value={"progress": 50}), _ACTOR)
    assert len(revised.assertions) == 2
    head = revised.assertions[-1]
    assert head.assertion_type is AssertionType.REVISION
    assert head.revises_assertion_id == dp.assertions[-1].id
    assert head.value == {"progress": 50}
    assert head.authored_by == _ACTOR


def test_revise_returns_new_instance_original_unchanged() -> None:
    dp = _data_point()
    revised = dp.revise(AssertionChange(value={"progress": 50}), _ACTOR)
    assert revised is not dp
    assert len(dp.assertions) == 1


def test_revision_history_is_chronological() -> None:
    dp = _data_point()
    r1 = dp.revise(AssertionChange(value={"progress": 25}), _ACTOR)
    r2 = r1.revise(AssertionChange(value={"progress": 75}), _ACTOR)
    history = r2.revision_history()
    assert [a.assertion_type for a in history] == [
        AssertionType.INITIAL,
        AssertionType.REVISION,
        AssertionType.REVISION,
    ]
    assert history[1].value == {"progress": 25}
    assert history[2].value == {"progress": 75}
    assert history[2].revises_assertion_id == history[1].id


def test_revisable_protocol_conformance() -> None:
    """DataPoint satisfies the Revisable Protocol per D125 (D114 conformance)."""
    assert isinstance(_data_point(), Revisable)
