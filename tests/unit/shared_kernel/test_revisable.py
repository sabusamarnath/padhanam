"""Unit tests for the Revisable Protocol and AssertionChange (D125, S43).

The protocol's behavioural semantics (revising appends, history is
chronological, latest is current) are exercised by the DataPoint
implementer's tests; these tests cover the AssertionChange value
object and the structural shape of the protocol itself.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from shared_kernel import AssertionChange, Revisable
from shared_kernel.actor_reference import ActorReference


def test_assertion_change_construction() -> None:
    change = AssertionChange(value={"status": "in-progress"})
    assert change.value == {"status": "in-progress"}


def test_assertion_change_is_frozen() -> None:
    change = AssertionChange(value={})
    with pytest.raises(FrozenInstanceError):
        change.value = {"x": 1}  # type: ignore[misc]


def test_assertion_change_none_value_rejected() -> None:
    with pytest.raises(ValueError, match="value"):
        AssertionChange(value=None)  # type: ignore[arg-type]


class _FakeRevisable:
    """Minimal structural implementer of Revisable for the conformance test."""

    def __init__(self) -> None:
        self._history: list[str] = []

    def revise(
        self, change: AssertionChange, actor: ActorReference
    ) -> "_FakeRevisable":
        self._history.append(f"{actor.user_id}:{change.value}")
        return self

    def revision_history(self) -> list[str]:
        return list(self._history)


def test_revisable_runtime_conformance() -> None:
    """A type carrying revise + revision_history satisfies Revisable."""
    assert isinstance(_FakeRevisable(), Revisable)


def test_non_revisable_fails_conformance() -> None:
    assert not isinstance(object(), Revisable)
