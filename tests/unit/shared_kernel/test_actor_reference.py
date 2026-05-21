"""Unit tests for the ActorReference placeholder value object (D124, S43)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from shared_kernel import ActorReference


def test_construction_happy_path() -> None:
    actor = ActorReference(user_id="operator")
    assert actor.user_id == "operator"


def test_is_frozen() -> None:
    actor = ActorReference(user_id="operator")
    with pytest.raises(FrozenInstanceError):
        actor.user_id = "other"  # type: ignore[misc]


def test_empty_user_id_rejected() -> None:
    with pytest.raises(ValueError, match="user_id"):
        ActorReference(user_id="")


def test_value_equality() -> None:
    """Frozen dataclasses use value equality — load-bearing for caches
    and cross-context comparisons."""
    a = ActorReference(user_id="operator")
    b = ActorReference(user_id="operator")
    assert a == b
    assert hash(a) == hash(b)
