"""Unit tests for the goal domain (S62, D163).

The typed goal layer: the LevelLadder mechanics (the adjustable qualitative
target) and the Goal value object's invariants. S62 instances only the
progressive shape; the enums carry the uninstanced values too.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from contexts.daily_driver.domain.goal import (
    ControlAxis,
    Goal,
    GoalMode,
    LevelLadder,
    Subject,
)

_TENANT = UUID("00000000-0000-4000-8000-00000000d001")
_OUTCOME = UUID("00000000-0000-4000-8000-0000000000a1")
_COMMITMENT = UUID("00000000-0000-4000-8000-0000000000b2")

_LADDER = ("A1", "A2", "B1", "B2", "C1", "C2")


def test_ladder_next_target_is_one_above_current() -> None:
    ladder = LevelLadder(levels=_LADDER, current_target_level="A2")
    assert ladder.next_target == "B1"
    assert ladder.current_index == 1
    assert ladder.is_at_top is False


def test_ladder_at_top_has_no_next_target() -> None:
    ladder = LevelLadder(levels=_LADDER, current_target_level="C2")
    assert ladder.is_at_top is True
    assert ladder.next_target is None


def test_ladder_rejects_target_not_on_ladder() -> None:
    with pytest.raises(ValueError):
        LevelLadder(levels=_LADDER, current_target_level="Z9")


def test_ladder_rejects_too_short_or_duplicate() -> None:
    with pytest.raises(ValueError):
        LevelLadder(levels=("A1",), current_target_level="A1")
    with pytest.raises(ValueError):
        LevelLadder(levels=("A1", "A1"), current_target_level="A1")


def test_progressive_goal_requires_ladder() -> None:
    with pytest.raises(ValueError):
        Goal(
            id=_OUTCOME,
            tenant_id=_TENANT,
            jurisdiction="eu-west",
            name="German",
            mode=GoalMode.PROGRESSIVE,
            control=ControlAxis.SELF,
            subject=Subject.SELF,
            lever_commitment_id=_COMMITMENT,
            ladder=None,
        )


def test_german_goal_is_constructable() -> None:
    goal = Goal(
        id=_OUTCOME,
        tenant_id=_TENANT,
        jurisdiction="eu-west",
        name="German",
        mode=GoalMode.PROGRESSIVE,
        control=ControlAxis.SELF,
        subject=Subject.SELF,
        lever_commitment_id=_COMMITMENT,
        ladder=LevelLadder(levels=_LADDER, current_target_level="A2"),
    )
    assert goal.mode is GoalMode.PROGRESSIVE
    assert goal.control is ControlAxis.SELF
    assert goal.subject is Subject.SELF
    assert goal.ladder is not None
    assert goal.ladder.next_target == "B1"
