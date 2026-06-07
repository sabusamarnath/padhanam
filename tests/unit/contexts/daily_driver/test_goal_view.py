"""Unit tests for build_goal_reading — the progressive read path (S62, D163).

The raise-or-hold remedy is qualitative and recommendation-shaped: RAISE only
when the lever is on track and the last observation met the current target; HOLD
otherwise (behind, not-met, not-yet-observed, at-top, or a missing lever). No
other mode's remedy fires.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from contexts.daily_driver.domain.commitment import (
    Commitment,
    CommitmentActivity,
    OutcomeStatus,
)
from contexts.daily_driver.domain.goal import (
    ControlAxis,
    Goal,
    GoalMode,
    LevelLadder,
    Subject,
)
from contexts.daily_driver.domain.goal_view import RaiseOrHold, build_goal_reading

_TENANT = UUID("00000000-0000-4000-8000-00000000d001")
_OUTCOME = UUID("00000000-0000-4000-8000-0000006200a1")
_COMMITMENT = UUID("00000000-0000-4000-8000-000000620c01")
_NOW = datetime(2026, 6, 7, 12, 0, tzinfo=timezone.utc)
_LADDER = ("A1", "A2", "B1", "B2", "C1", "C2")


def _goal(target: str = "B1") -> Goal:
    return Goal(
        id=_OUTCOME,
        tenant_id=_TENANT,
        jurisdiction="eu-west",
        name="German",
        mode=GoalMode.PROGRESSIVE,
        control=ControlAxis.SELF,
        subject=Subject.SELF,
        lever_commitment_id=_COMMITMENT,
        ladder=LevelLadder(levels=_LADDER, current_target_level=target),
    )


def _activity(
    *, last_completed_at: datetime | None, status: OutcomeStatus | None
) -> CommitmentActivity:
    commitment = Commitment(
        id=_COMMITMENT,
        tenant_id=_TENANT,
        jurisdiction="eu-west",
        name="German practice",
        expected_interval_days=1,
        authored_by_user_id="operator-001",
        created_at=_NOW - timedelta(days=30),
        expected_outcome="toward fluency",
        observed_outcome="solid week" if status is not None else None,
        outcome_status=status,
        observed_at=_NOW - timedelta(hours=2) if status is not None else None,
    )
    return CommitmentActivity(
        commitment=commitment, last_completed_at=last_completed_at
    )


def test_on_track_and_met_recommends_raise() -> None:
    activity = _activity(
        last_completed_at=_NOW - timedelta(hours=6), status=OutcomeStatus.MET
    )
    reading = build_goal_reading(goal=_goal(), activity=activity, now=_NOW)
    assert reading.recommendation is RaiseOrHold.RAISE
    assert reading.next_target == "B2"
    assert reading.current_target == "B1"


def test_behind_recommends_hold() -> None:
    activity = _activity(
        last_completed_at=_NOW - timedelta(days=10), status=OutcomeStatus.MET
    )
    reading = build_goal_reading(goal=_goal(), activity=activity, now=_NOW)
    assert reading.recommendation is RaiseOrHold.HOLD
    assert "behind" in reading.progress_summary


def test_on_track_but_not_met_recommends_hold() -> None:
    activity = _activity(
        last_completed_at=_NOW - timedelta(hours=6),
        status=OutcomeStatus.PARTIAL,
    )
    reading = build_goal_reading(goal=_goal(), activity=activity, now=_NOW)
    assert reading.recommendation is RaiseOrHold.HOLD


def test_no_observation_yet_recommends_hold() -> None:
    activity = _activity(
        last_completed_at=_NOW - timedelta(hours=6), status=None
    )
    reading = build_goal_reading(goal=_goal(), activity=activity, now=_NOW)
    assert reading.recommendation is RaiseOrHold.HOLD
    assert "no observation" in reading.progress_summary


def test_at_top_of_ladder_holds_with_no_next() -> None:
    activity = _activity(
        last_completed_at=_NOW - timedelta(hours=6), status=OutcomeStatus.MET
    )
    reading = build_goal_reading(goal=_goal(target="C2"), activity=activity, now=_NOW)
    assert reading.recommendation is RaiseOrHold.HOLD
    assert reading.next_target is None


def test_missing_lever_holds() -> None:
    reading = build_goal_reading(goal=_goal(), activity=None, now=_NOW)
    assert reading.recommendation is RaiseOrHold.HOLD
    assert "not found" in reading.progress_summary


def test_non_progressive_goal_is_not_read_at_s62() -> None:
    goal = Goal(
        id=_OUTCOME,
        tenant_id=_TENANT,
        jurisdiction="eu-west",
        name="Steady reading",
        mode=GoalMode.HOMEOSTATIC,
        control=ControlAxis.SELF,
        subject=Subject.SELF,
        lever_commitment_id=_COMMITMENT,
        ladder=None,
    )
    activity = _activity(
        last_completed_at=_NOW - timedelta(hours=6), status=OutcomeStatus.MET
    )
    reading = build_goal_reading(goal=goal, activity=activity, now=_NOW)
    assert reading.recommendation is RaiseOrHold.HOLD
    assert "homeostatic" in reading.reason
