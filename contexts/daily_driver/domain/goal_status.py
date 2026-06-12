"""Goal status taxonomy — the per-goal verdict (D187, S92).

One status per goal, computed from its commitments' cadence adherence and its
confirmed-edge activity. A read recomputed from the moat each time, never stored.

The status family is set by the goal's mode (Step-0 reconciled — every goal
carries commitments, so mode, not commitment-presence, is the split):

- **homeostatic** (holds a level by repeating — the rhythm *is* the goal) is a
  **cadence goal**: on-track / behind / stalled by its lever commitments' cadence
  adherence, worst-status-wins across levers. Its signal is the commitment
  completion log (user-owned), so a dead habit reads stalled even with no edges.
- **progressive** (raises a level — no rhythm to slip) is **cadence-less**:
  active / stalled by confirmed-edge activity recency, never behind.
- **sequence** reads **done** when its terminal is reached, else by activity.

Missed beats reuse the existing staleness math (``overdue_by_days // interval``).
Thresholds are static config this session (D187); the adaptive K-per-goal loop
is post-week. Pure domain (D16): stdlib + the daily-driver value objects only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from contexts.daily_driver.domain.commitment import CommitmentActivity
from contexts.daily_driver.domain.goal import Goal, GoalMode, TerminalState
from contexts.daily_driver.domain.staleness import (
    days_elapsed,
    is_overdue,
    overdue_by_days,
)


class GoalStatus(str, Enum):
    """The verdict per goal (D187, D188).

    ``ASLEEP`` (D188) is the progressive middle gear: recent activity, but the
    practice commitment has lapsed — a paused practice, not a dead one.
    """

    ON_TRACK = "on_track"
    BEHIND = "behind"
    STALLED = "stalled"
    DONE = "done"
    ACTIVE = "active"
    ASLEEP = "asleep"


@dataclass(frozen=True)
class GoalStatusThresholds:
    """Static status thresholds (D187, S92) — tunable config, not the decision.

    ``daily_stalled_k`` applies to a daily lever (interval <= 1 day);
    ``weekly_stalled_k`` to any longer cadence. ``no_activity_window_days`` is
    the cadence-less active/stalled boundary.
    """

    daily_stalled_k: int = 3
    weekly_stalled_k: int = 2
    no_activity_window_days: int = 14


DEFAULT_GOAL_STATUS_THRESHOLDS = GoalStatusThresholds()

# Worst-status-wins ordering for a cadence goal's several levers (D177): a goal
# with one dead habit is at-risk. Lower rank = worse.
_CADENCE_RANK = {
    GoalStatus.STALLED: 0,
    GoalStatus.BEHIND: 1,
    GoalStatus.ON_TRACK: 2,
}


def _goal_lever_ids(goal: Goal) -> tuple[UUID, ...]:
    """Every Postgres commitment id that levers the goal (D177), deduped."""
    ids: list[UUID] = []
    seen: set[UUID] = set()
    for cid in (
        goal.lever_commitment_id,
        *goal.lever_commitment_ids,
        *(step.commitment_id for step in goal.steps),
    ):
        if cid is not None and cid not in seen:
            seen.add(cid)
            ids.append(cid)
    return tuple(ids)


def _lever_verdict(
    activity: CommitmentActivity,
    *,
    now: datetime,
    thresholds: GoalStatusThresholds,
) -> tuple[GoalStatus, int]:
    """(status, overdue_days) for one lever, by cadence adherence."""
    commitment = activity.commitment
    last = activity.last_completed_at or commitment.created_at
    interval = commitment.expected_interval_days
    overdue = overdue_by_days(
        last_activity_at=last, expected_interval_days=interval, now=now
    )
    if not is_overdue(
        last_activity_at=last, expected_interval_days=interval, now=now
    ):
        return (GoalStatus.ON_TRACK, 0)
    k = thresholds.daily_stalled_k if interval <= 1 else thresholds.weekly_stalled_k
    status = GoalStatus.STALLED if overdue // interval >= k else GoalStatus.BEHIND
    return (status, overdue)


def _commitment_status(
    activity: CommitmentActivity,
    *,
    now: datetime,
    thresholds: GoalStatusThresholds,
) -> GoalStatus:
    return _lever_verdict(activity, now=now, thresholds=thresholds)[0]


@dataclass(frozen=True)
class GoalVerdict:
    """A goal's status plus the one-phrase why drawn from its evidence (D189)."""

    status: GoalStatus
    why: str


def compute_goal_verdict(
    *,
    goal: Goal,
    commitment_activities: dict[UUID, CommitmentActivity],
    latest_activity_at: datetime | None,
    now: datetime,
    thresholds: GoalStatusThresholds = DEFAULT_GOAL_STATUS_THRESHOLDS,
) -> GoalVerdict:
    """The goal's status + a short evidence-drawn why (D187/D188/D189).

    ``commitment_activities`` maps a commitment id to its activity (cadence +
    last completion). ``latest_activity_at`` is the most recent confirmed-edge
    activity for the goal (None when it has none).
    """
    # A completed sequence reads done.
    if (
        goal.mode is GoalMode.SEQUENCE
        and goal.terminal is not None
        and goal.terminal.state is TerminalState.REACHED
    ):
        return GoalVerdict(GoalStatus.DONE, "reached")

    # Cadence goal (homeostatic): the commitment completion log is the signal.
    if goal.mode is GoalMode.HOMEOSTATIC:
        levers = [
            commitment_activities[cid]
            for cid in _goal_lever_ids(goal)
            if cid in commitment_activities
        ]
        if levers:
            verdicts = [
                _lever_verdict(a, now=now, thresholds=thresholds) for a in levers
            ]
            status, overdue = min(  # worst-status-wins (D177)
                verdicts, key=lambda v: _CADENCE_RANK[v[0]]
            )
            why = "on rhythm" if status is GoalStatus.ON_TRACK else f"{overdue}d overdue"
            return GoalVerdict(status, why)

    # Cadence-less (progressive / sequence-not-done / homeostatic-without-levers).
    quiet = (
        days_elapsed(since=latest_activity_at, now=now)
        if latest_activity_at is not None
        else None
    )
    # 1. No recent confirmed activity in the window — at-risk, surfaced not
    #    hidden (D187). Covers the no-signal fallback too (latest is None).
    if quiet is None or quiet > thresholds.no_activity_window_days:
        why = f"quiet {quiet}d" if quiet is not None else "no activity yet"
        return GoalVerdict(GoalStatus.STALLED, why)
    # 2. A progressive goal with a lapsed practice commitment reads asleep (D188):
    #    recent activity exists, but the intended practice is being skipped.
    if goal.mode is GoalMode.PROGRESSIVE:
        practice = [
            commitment_activities[cid]
            for cid in _goal_lever_ids(goal)
            if cid in commitment_activities
        ]
        if practice and any(
            _commitment_status(a, now=now, thresholds=thresholds)
            is GoalStatus.STALLED
            for a in practice
        ):
            return GoalVerdict(GoalStatus.ASLEEP, "practice paused")
    # 3. Recent activity, no lapse — active.
    why = "today" if quiet == 0 else f"{quiet}d ago"
    return GoalVerdict(GoalStatus.ACTIVE, why)


def compute_goal_status(
    *,
    goal: Goal,
    commitment_activities: dict[UUID, CommitmentActivity],
    latest_activity_at: datetime | None,
    now: datetime,
    thresholds: GoalStatusThresholds = DEFAULT_GOAL_STATUS_THRESHOLDS,
) -> GoalStatus:
    """The goal's one status (D187/D188). Delegates to ``compute_goal_verdict``."""
    return compute_goal_verdict(
        goal=goal,
        commitment_activities=commitment_activities,
        latest_activity_at=latest_activity_at,
        now=now,
        thresholds=thresholds,
    ).status


__all__ = [
    "DEFAULT_GOAL_STATUS_THRESHOLDS",
    "GoalStatus",
    "GoalStatusThresholds",
    "GoalVerdict",
    "compute_goal_status",
    "compute_goal_verdict",
]
