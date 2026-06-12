"""Unit tests for the goal status taxonomy (D187, S92).

Synthetic goals/commitments only — no PII. now is injected for determinism.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from contexts.daily_driver.domain.commitment import (
    Commitment,
    CommitmentActivity,
)
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
from contexts.daily_driver.domain.goal_status import (
    GoalStatus,
    GoalStatusThresholds,
    compute_goal_status,
)

_TENANT = UUID("00000000-0000-4000-8000-00000000d001")
_NOW = datetime(2026, 6, 12, tzinfo=timezone.utc)
_TH = GoalStatusThresholds()  # daily K=3, weekly K=2, window 14d


def _commitment(interval: int, cid: UUID | None = None) -> Commitment:
    return Commitment(
        id=cid or uuid4(),
        tenant_id=_TENANT,
        jurisdiction="eu-west",
        name="habit",
        expected_interval_days=interval,
        authored_by_user_id="op",
        created_at=_NOW - timedelta(days=365),
    )


def _activity(commitment: Commitment, *, last_days_ago: int | None) -> CommitmentActivity:
    last = None if last_days_ago is None else _NOW - timedelta(days=last_days_ago)
    return CommitmentActivity(commitment=commitment, last_completed_at=last)


def _homeostatic(lever_ids: tuple[UUID, ...]) -> Goal:
    return Goal(
        id=uuid4(), tenant_id=_TENANT, jurisdiction="eu-west", name="Habit goal",
        mode=GoalMode.HOMEOSTATIC, control=ControlAxis.SELF, subject=Subject.SELF,
        lever_commitment_ids=lever_ids,
    )


def _progressive() -> Goal:
    return Goal(
        id=uuid4(), tenant_id=_TENANT, jurisdiction="eu-west", name="German",
        mode=GoalMode.PROGRESSIVE, control=ControlAxis.SELF, subject=Subject.SELF,
        lever_commitment_id=uuid4(),
        ladder=LevelLadder(levels=("A1", "A2", "B1"), current_target_level="A2"),
    )


def _sequence(*, reached: bool) -> Goal:
    return Goal(
        id=uuid4(), tenant_id=_TENANT, jurisdiction="eu-west", name="Get a job",
        mode=GoalMode.SEQUENCE, control=ControlAxis.SELF, subject=Subject.SELF,
        terminal=Terminal(
            target="Offer accepted",
            state=TerminalState.REACHED if reached else TerminalState.PENDING,
        ),
        steps=(LeverStep(commitment_id=uuid4(), order=1, state=StepState.READY),),
    )


def _status(goal, activities=None, latest=None):
    return compute_goal_status(
        goal=goal,
        commitment_activities=activities or {},
        latest_activity_at=latest,
        now=_NOW,
        thresholds=_TH,
    )


# --- cadence (homeostatic) at each boundary -------------------------------

def test_daily_cadence_on_track_behind_stalled_boundaries() -> None:
    c = _commitment(1)
    goal = _homeostatic((c.id,))
    # not overdue -> on_track
    assert _status(goal, {c.id: _activity(c, last_days_ago=1)}) is GoalStatus.ON_TRACK
    # 2-3 days -> 1-2 missed -> behind
    assert _status(goal, {c.id: _activity(c, last_days_ago=2)}) is GoalStatus.BEHIND
    assert _status(goal, {c.id: _activity(c, last_days_ago=3)}) is GoalStatus.BEHIND
    # 4 days -> 3 missed (K=3) -> stalled
    assert _status(goal, {c.id: _activity(c, last_days_ago=4)}) is GoalStatus.STALLED


def test_weekly_cadence_boundaries() -> None:
    c = _commitment(7)
    goal = _homeostatic((c.id,))
    assert _status(goal, {c.id: _activity(c, last_days_ago=7)}) is GoalStatus.ON_TRACK
    # 14 days -> 1 missed -> behind
    assert _status(goal, {c.id: _activity(c, last_days_ago=14)}) is GoalStatus.BEHIND
    # 21 days -> 2 missed (K=2) -> stalled
    assert _status(goal, {c.id: _activity(c, last_days_ago=21)}) is GoalStatus.STALLED


def test_worst_status_wins_across_levers() -> None:
    on_track = _commitment(1)
    stalled = _commitment(1)
    goal = _homeostatic((on_track.id, stalled.id))
    activities = {
        on_track.id: _activity(on_track, last_days_ago=1),  # on_track
        stalled.id: _activity(stalled, last_days_ago=10),   # stalled
    }
    # one dead habit drags the goal to stalled (the at-risk read)
    assert _status(goal, activities) is GoalStatus.STALLED


def test_never_completed_daily_habit_reads_stalled() -> None:
    c = _commitment(1)  # created 365d ago, never completed
    goal = _homeostatic((c.id,))
    assert _status(goal, {c.id: _activity(c, last_days_ago=None)}) is GoalStatus.STALLED


# --- cadence-less (progressive) -------------------------------------------

def test_progressive_active_within_window_stalled_past() -> None:
    goal = _progressive()
    # cannot be behind; active within 14d of activity
    assert _status(goal, latest=_NOW - timedelta(days=3)) is GoalStatus.ACTIVE
    assert _status(goal, latest=_NOW - timedelta(days=20)) is GoalStatus.STALLED


def test_progressive_ignores_commitment_cadence() -> None:
    # a progressive goal's never-completed daily lever does NOT make it behind;
    # it reads by edge activity only (cadence-less).
    goal = _progressive()
    assert _status(goal, latest=_NOW - timedelta(days=1)) is GoalStatus.ACTIVE


# --- sequence -------------------------------------------------------------

def test_sequence_reached_reads_done() -> None:
    assert _status(_sequence(reached=True)) is GoalStatus.DONE


def test_sequence_pending_reads_by_activity() -> None:
    goal = _sequence(reached=False)
    assert _status(goal, latest=_NOW - timedelta(days=2)) is GoalStatus.ACTIVE
    assert _status(goal, latest=_NOW - timedelta(days=30)) is GoalStatus.STALLED


# --- the no-signal fallback ----------------------------------------------

def test_no_commitments_and_no_activity_reads_stalled() -> None:
    goal = _progressive()  # cadence-less, no activity, no commitment signal read
    assert _status(goal, latest=None) is GoalStatus.STALLED
