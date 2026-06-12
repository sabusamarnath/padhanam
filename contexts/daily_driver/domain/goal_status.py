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
    """The verdict per goal (D187)."""

    ON_TRACK = "on_track"
    BEHIND = "behind"
    STALLED = "stalled"
    DONE = "done"
    ACTIVE = "active"


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


def _commitment_status(
    activity: CommitmentActivity,
    *,
    now: datetime,
    thresholds: GoalStatusThresholds,
) -> GoalStatus:
    """on-track / behind / stalled for one lever, by cadence adherence."""
    commitment = activity.commitment
    last = activity.last_completed_at or commitment.created_at
    interval = commitment.expected_interval_days
    if not is_overdue(
        last_activity_at=last, expected_interval_days=interval, now=now
    ):
        return GoalStatus.ON_TRACK
    missed = (
        overdue_by_days(
            last_activity_at=last, expected_interval_days=interval, now=now
        )
        // interval
    )
    k = thresholds.daily_stalled_k if interval <= 1 else thresholds.weekly_stalled_k
    return GoalStatus.STALLED if missed >= k else GoalStatus.BEHIND


def compute_goal_status(
    *,
    goal: Goal,
    commitment_activities: dict[UUID, CommitmentActivity],
    latest_activity_at: datetime | None,
    now: datetime,
    thresholds: GoalStatusThresholds = DEFAULT_GOAL_STATUS_THRESHOLDS,
) -> GoalStatus:
    """The goal's one status (D187).

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
        return GoalStatus.DONE

    # Cadence goal (homeostatic): the commitment completion log is the signal.
    if goal.mode is GoalMode.HOMEOSTATIC:
        levers = [
            commitment_activities[cid]
            for cid in _goal_lever_ids(goal)
            if cid in commitment_activities
        ]
        if levers:
            statuses = [
                _commitment_status(a, now=now, thresholds=thresholds)
                for a in levers
            ]
            return min(statuses, key=lambda s: _CADENCE_RANK[s])  # worst-wins

    # Cadence-less (progressive / sequence-not-done / homeostatic-without-levers):
    # active within the no-activity window of confirmed-edge activity, else stalled.
    if latest_activity_at is not None:
        if (
            days_elapsed(since=latest_activity_at, now=now)
            <= thresholds.no_activity_window_days
        ):
            return GoalStatus.ACTIVE
        return GoalStatus.STALLED

    # No commitment signal and no activity — at-risk, surfaced not hidden (D187).
    return GoalStatus.STALLED


__all__ = [
    "DEFAULT_GOAL_STATUS_THRESHOLDS",
    "GoalStatus",
    "GoalStatusThresholds",
    "compute_goal_status",
]
