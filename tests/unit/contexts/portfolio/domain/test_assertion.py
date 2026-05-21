"""Unit tests for the Assertion domain entity (D124, S43)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contexts.portfolio.domain import Assertion, AssertionType
from shared_kernel import ActorReference

_ACTOR = ActorReference(user_id="operator")


def _initial() -> Assertion:
    return Assertion(
        id=uuid4(),
        data_point_id=uuid4(),
        tenant_id=uuid4(),
        jurisdiction="eu-west",
        assertion_type=AssertionType.INITIAL,
        revises_assertion_id=None,
        value={"status": "open"},
        authored_by=_ACTOR,
        created_at=datetime.now(timezone.utc),
    )


def test_initial_construction() -> None:
    a = _initial()
    assert a.assertion_type is AssertionType.INITIAL
    assert a.revises_assertion_id is None


def test_revision_construction() -> None:
    prior = uuid4()
    a = Assertion(
        id=uuid4(),
        data_point_id=uuid4(),
        tenant_id=uuid4(),
        jurisdiction="eu-west",
        assertion_type=AssertionType.REVISION,
        revises_assertion_id=prior,
        value={"status": "done"},
        authored_by=_ACTOR,
        created_at=datetime.now(timezone.utc),
    )
    assert a.revises_assertion_id == prior


def test_is_frozen() -> None:
    a = _initial()
    with pytest.raises(FrozenInstanceError):
        a.value = {}  # type: ignore[misc]


def test_empty_jurisdiction_rejected() -> None:
    with pytest.raises(ValueError, match="jurisdiction"):
        Assertion(
            id=uuid4(),
            data_point_id=uuid4(),
            tenant_id=uuid4(),
            jurisdiction="",
            assertion_type=AssertionType.INITIAL,
            revises_assertion_id=None,
            value={},
            authored_by=_ACTOR,
            created_at=datetime.now(timezone.utc),
        )


def test_initial_with_revises_id_rejected() -> None:
    with pytest.raises(ValueError, match="INITIAL"):
        Assertion(
            id=uuid4(),
            data_point_id=uuid4(),
            tenant_id=uuid4(),
            jurisdiction="eu-west",
            assertion_type=AssertionType.INITIAL,
            revises_assertion_id=uuid4(),
            value={},
            authored_by=_ACTOR,
            created_at=datetime.now(timezone.utc),
        )


def test_revision_without_revises_id_rejected() -> None:
    with pytest.raises(ValueError, match="REVISION"):
        Assertion(
            id=uuid4(),
            data_point_id=uuid4(),
            tenant_id=uuid4(),
            jurisdiction="eu-west",
            assertion_type=AssertionType.REVISION,
            revises_assertion_id=None,
            value={},
            authored_by=_ACTOR,
            created_at=datetime.now(timezone.utc),
        )
