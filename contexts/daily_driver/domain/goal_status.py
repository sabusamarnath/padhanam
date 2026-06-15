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
from datetime import datetime, time, timezone
from enum import Enum
from typing import NamedTuple
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
    # D191: a cadence commitment with no completion evidence reads not-tracked —
    # the honest "the moat does not know whether the work happened," never a
    # verdict fabricated from the commitment's age (its ``created_at``).
    NOT_TRACKED = "not_tracked"


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


class LeverVerdict(NamedTuple):
    """One lever's verdict: status, overdue days, and whether a reported miss
    drove it (``evidenced`` — a tracked negative, not an inference)."""

    status: GoalStatus
    overdue_days: int
    evidenced: bool


def _staleness(last: datetime, interval: int, now: datetime) -> tuple[bool, int]:
    """(is_overdue, overdue_days) for an activity time against the interval."""
    return (
        is_overdue(last_activity_at=last, expected_interval_days=interval, now=now),
        overdue_by_days(
            last_activity_at=last, expected_interval_days=interval, now=now
        ),
    )


def _lever_verdict(
    activity: CommitmentActivity,
    *,
    now: datetime,
    thresholds: GoalStatusThresholds,
) -> LeverVerdict:
    """The three-state cadence verdict for one lever (D192).

    A recent **did** reads the existing cadence verdict (on-track / behind /
    stalled by overdue). A **reported-didn't** is a tracked negative — a
    confirmed miss can never read on-track, so it reads behind or stalled *with
    evidence*. **Neither** (silence) reads not-tracked — the lever's age never
    fabricates a verdict (D191; the ``created_at`` fallback is gone)."""
    commitment = activity.commitment
    interval = commitment.expected_interval_days
    k = thresholds.daily_stalled_k if interval <= 1 else thresholds.weekly_stalled_k
    last_did = activity.last_completed_at
    last_didnt = activity.last_reported_didnt  # a beat date | None

    if last_did is None and last_didnt is None:
        return LeverVerdict(GoalStatus.NOT_TRACKED, 0, False)

    # Case A — a completion exists: read its cadence, but a reported miss after
    # the last did is a confirmed lapse since completion (never on-track).
    if last_did is not None:
        overdue_now, overdue = _staleness(last_did, interval, now)
        didnt_after_did = last_didnt is not None and last_didnt > last_did.date()
        if not overdue_now:
            if didnt_after_did:
                return LeverVerdict(GoalStatus.BEHIND, interval, True)
            return LeverVerdict(GoalStatus.ON_TRACK, 0, False)
        status = (
            GoalStatus.STALLED if overdue // interval >= k else GoalStatus.BEHIND
        )
        return LeverVerdict(status, overdue, didnt_after_did)

    # Case B — no completion ever, but reported misses exist: confirmed misses,
    # never on-track. With no completion baseline the magnitude is the *count*
    # of confirmed misses (K reads stalled), never the silent days between them
    # (D192 — silence is not a miss). ``overdue_days`` carries days since the
    # latest reported beat for the why.
    didnt_dt = datetime.combine(last_didnt, time.min, tzinfo=timezone.utc)
    days_since = days_elapsed(since=didnt_dt, now=now)
    status = (
        GoalStatus.STALLED
        if activity.reported_didnt_count >= k
        else GoalStatus.BEHIND
    )
    return LeverVerdict(status, days_since, True)


def compute_lever_status(
    activity: CommitmentActivity,
    *,
    now: datetime,
    thresholds: GoalStatusThresholds = DEFAULT_GOAL_STATUS_THRESHOLDS,
) -> GoalStatus:
    """One lever's status (D191/D192) — ``NOT_TRACKED`` when there is neither a
    completion nor a reported miss (silence), else its three-state cadence
    verdict. Lets the evidence surface show which levers have no data even while
    the goal as a whole reads a verdict (the partial-tracking rule)."""
    return _lever_verdict(activity, now=now, thresholds=thresholds).status


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
            # D191/D192: read the cadence verdict from the *evidenced* levers
            # only — those with a completion or a reported miss. A silent lever
            # (neither) never fabricates a verdict (its age is not evidence) nor
            # drags the goal down. The goal reads not-tracked only when NO lever
            # has any evidence (the partial-tracking rule).
            evidenced = [
                a
                for a in levers
                if a.last_completed_at is not None
                or a.last_reported_didnt is not None
            ]
            if not evidenced:
                return GoalVerdict(GoalStatus.NOT_TRACKED, "not tracked")
            verdicts = [
                _lever_verdict(a, now=now, thresholds=thresholds)
                for a in evidenced
            ]
            worst = min(  # worst-status-wins (D177)
                verdicts, key=lambda v: _CADENCE_RANK[v.status]
            )
            if worst.status is GoalStatus.ON_TRACK:
                why = "on rhythm"
            elif worst.evidenced:
                # a confirmed miss (reported), not an inference from absence
                why = f"missed {worst.overdue_days}d (reported)"
            else:
                why = f"{worst.overdue_days}d overdue"
            return GoalVerdict(worst.status, why)

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
    #    D192: the lapse must be *evidenced* — a practice lever with no
    #    completion and no reported miss reads not-tracked (compute_lever_status),
    #    so it no longer fabricates asleep from the commitment's age (the S96
    #    residual, now fixed); only a real lapse (stale did, or reported miss)
    #    drives asleep.
    if goal.mode is GoalMode.PROGRESSIVE:
        practice = [
            commitment_activities[cid]
            for cid in _goal_lever_ids(goal)
            if cid in commitment_activities
        ]
        if practice and any(
            compute_lever_status(a, now=now, thresholds=thresholds)
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
    "compute_lever_status",
]
