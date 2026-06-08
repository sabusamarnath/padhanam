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
    LeverStep,
    StepState,
    Subject,
    Terminal,
    TerminalState,
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


# --- sequence goal (S63, D163) --------------------------------------------


def _sequence_goal() -> Goal:
    return Goal(
        id=_OUTCOME,
        tenant_id=_TENANT,
        jurisdiction="eu-west",
        name="Get a job",
        mode=GoalMode.SEQUENCE,
        control=ControlAxis.OTHER,  # the influence case
        subject=Subject.SELF,
        terminal=Terminal(target="Offer accepted", state=TerminalState.PENDING),
        steps=(
            LeverStep(commitment_id=_COMMITMENT, order=2, state=StepState.BLOCKED),
            LeverStep(
                commitment_id=UUID("00000000-0000-4000-8000-0000000000b3"),
                order=1,
                state=StepState.DONE,
            ),
        ),
    )


def test_sequence_goal_orders_its_steps() -> None:
    goal = _sequence_goal()
    assert goal.mode is GoalMode.SEQUENCE
    assert goal.control is ControlAxis.OTHER
    assert goal.terminal is not None
    assert goal.terminal.state is TerminalState.PENDING
    # ordered_steps sorts by the 1-based release order.
    assert [s.order for s in goal.ordered_steps] == [1, 2]
    assert goal.ordered_steps[0].state is StepState.DONE


def test_sequence_goal_requires_terminal_and_steps() -> None:
    with pytest.raises(ValueError):
        Goal(
            id=_OUTCOME,
            tenant_id=_TENANT,
            jurisdiction="eu-west",
            name="Get a job",
            mode=GoalMode.SEQUENCE,
            control=ControlAxis.OTHER,
            subject=Subject.SELF,
            terminal=None,
            steps=(),
        )


def test_progressive_goal_requires_lever_commitment() -> None:
    with pytest.raises(ValueError):
        Goal(
            id=_OUTCOME,
            tenant_id=_TENANT,
            jurisdiction="eu-west",
            name="German",
            mode=GoalMode.PROGRESSIVE,
            control=ControlAxis.SELF,
            subject=Subject.SELF,
            lever_commitment_id=None,
            ladder=LevelLadder(levels=_LADDER, current_target_level="A2"),
        )
