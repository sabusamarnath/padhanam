"""build_goal_reading — read the progressive goal against its lever (S62, D163).

Pure domain logic. For a progressive-cadence goal, the adjustable target is a
live expected-versus-observed loop: the current target is the expectation,
progress is the observed (drawn from the lever commitment), and the qualitative
gap drives a raise-or-hold recommendation.

S62 reads only the progressive shape (German). The recommendation is
recommendation-shaped (D9): the function returns a RAISE/HOLD recommendation
with a reason; the target changes only on the operator's explicit raise action,
never here. The remedies for the other modes (homeostatic re-establish, sequence
unblock-or-drop) are deliberately absent — they arrive with the session that
instances a goal of that shape, so the wrong remedy cannot fire on a cadence
goal (D163).

The gap is qualitative, not numeric — quantitative target inference stays
deferred per D156. ``now`` is injected by the application layer; the domain
stays pure and deterministic per D16.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from contexts.daily_driver.domain.commitment import (
    CommitmentActivity,
    OutcomeStatus,
)
from contexts.daily_driver.domain.goal import (
    Goal,
    GoalMode,
    StepState,
    TerminalState,
)
from contexts.daily_driver.domain.staleness import is_overdue, overdue_by_days


class RaiseOrHold(str, Enum):
    """The progressive remedy at S62: raise the target, or hold it."""

    RAISE = "raise"
    HOLD = "hold"


class UnblockOrDrop(str, Enum):
    """The sequence remedy (S63): unblock the active step, drop it, or continue.

    Distinct from ``RaiseOrHold`` by construction — the two remedies share no
    code path (D163: the remedy reads the shape; the wrong remedy must not fire
    on the wrong mode). ``UNBLOCK`` and ``DROP`` are the two interventions on a
    stalled step (the actor's call, recommendation-shaped per D9); ``CONTINUE``
    is the no-intervention default (the chain is moving).
    """

    UNBLOCK = "unblock"
    DROP = "drop"
    CONTINUE = "continue"


@dataclass(frozen=True)
class GoalReading:
    """A progressive goal read against its lever (D163).

    ``current_target`` is the level the goal aims at now; ``progress_summary``
    is the qualitative observed progress from the lever commitment;
    ``gap_summary`` is the qualitative gap between the two; ``recommendation``
    is the raise-or-hold remedy with its reason; ``next_target`` is the level a
    raise would move to (``None`` at the top of the ladder).
    """

    goal: Goal
    current_target: str | None
    progress_summary: str
    gap_summary: str
    recommendation: RaiseOrHold
    reason: str
    next_target: str | None


def _cadence_on_track(activity: CommitmentActivity, *, now: datetime) -> bool:
    commitment = activity.commitment
    last_activity = activity.last_completed_at or commitment.created_at
    return not is_overdue(
        last_activity_at=last_activity,
        expected_interval_days=commitment.expected_interval_days,
        now=now,
    )


def _cadence_phrase(activity: CommitmentActivity, *, now: datetime) -> str:
    commitment = activity.commitment
    last_activity = activity.last_completed_at or commitment.created_at
    if _cadence_on_track(activity, now=now):
        return f"on track (every {commitment.expected_interval_days} days)"
    overshoot = overdue_by_days(
        last_activity_at=last_activity,
        expected_interval_days=commitment.expected_interval_days,
        now=now,
    )
    plural = "s" if overshoot != 1 else ""
    return f"behind — {overshoot} day{plural} over"


def _observation_phrase(activity: CommitmentActivity) -> str:
    status = activity.commitment.outcome_status
    if status is None:
        return "no observation recorded yet"
    note = activity.commitment.observed_outcome
    if note:
        return f"last observed: {status.value} — {note}"
    return f"last observed: {status.value}"


def build_goal_reading(
    *,
    goal: Goal,
    activity: CommitmentActivity | None,
    now: datetime,
) -> GoalReading:
    """Read a progressive goal against its lever commitment (D163).

    ``activity`` is the lever commitment's activity (``None`` when the lever is
    absent — the reading then holds and says so). Only the progressive shape is
    read at S62; a non-progressive goal returns a hold with a shape-aware note
    rather than a fabricated cadence remedy.
    """
    ladder = goal.ladder
    current_target = ladder.current_target_level if ladder is not None else None
    next_target = ladder.next_target if ladder is not None else None

    if goal.mode is not GoalMode.PROGRESSIVE or ladder is None:
        # Out of S62 scope: no remedy beyond a hold; the shape's remedy lands
        # with the session that instances it (D163).
        return GoalReading(
            goal=goal,
            current_target=current_target,
            progress_summary="not read at S62 (only progressive goals are read)",
            gap_summary="—",
            recommendation=RaiseOrHold.HOLD,
            reason=f"the {goal.mode.value} remedy is not wired yet",
            next_target=next_target,
        )

    if activity is None:
        return GoalReading(
            goal=goal,
            current_target=current_target,
            progress_summary="lever commitment not found",
            gap_summary=f"cannot read progress toward {current_target}",
            recommendation=RaiseOrHold.HOLD,
            reason="no lever to read progress from",
            next_target=next_target,
        )

    cadence = _cadence_phrase(activity, now=now)
    observation = _observation_phrase(activity)
    progress_summary = f"Lever '{activity.commitment.name}': {cadence}; {observation}"

    on_track = _cadence_on_track(activity, now=now)
    met = activity.commitment.outcome_status is OutcomeStatus.MET
    sustained = on_track and met

    if ladder.is_at_top:
        return GoalReading(
            goal=goal,
            current_target=current_target,
            progress_summary=progress_summary,
            gap_summary=f"at the top of the ladder ({current_target})",
            recommendation=RaiseOrHold.HOLD,
            reason="already at the top of the ladder — nothing higher to raise to",
            next_target=None,
        )

    if sustained:
        return GoalReading(
            goal=goal,
            current_target=current_target,
            progress_summary=progress_summary,
            gap_summary=(
                f"sustaining {current_target}; ready to reach for {next_target}"
            ),
            recommendation=RaiseOrHold.RAISE,
            reason=(
                f"the lever is on track and the last observation met "
                f"{current_target} — raise the target to {next_target}"
            ),
            next_target=next_target,
        )

    return GoalReading(
        goal=goal,
        current_target=current_target,
        progress_summary=progress_summary,
        gap_summary=f"progress toward {current_target} is not yet sustained",
        recommendation=RaiseOrHold.HOLD,
        reason=(
            "hold the target — "
            + (
                "the lever is behind its rhythm"
                if not on_track
                else "the last observation hasn't met the current target"
            )
        ),
        next_target=next_target,
    )


# --- sequence reading (S63, D163): unblock-or-drop, reads the chain shape ----


@dataclass(frozen=True)
class StepReading:
    """One lever step rendered for the chain view (S63)."""

    name: str
    order: int
    state: StepState
    is_active: bool


@dataclass(frozen=True)
class ChainReading:
    """A sequence goal read against its lever-step chain (D163, S63).

    The sequence analogue of ``GoalReading`` — a deliberately separate type so
    no read path crosses the two remedies. ``terminal_state`` is the
    influence-gated terminal (the part another party decides); its richer
    probabilistic reading is deferred to the influence instance.
    """

    goal: Goal
    terminal_target: str | None
    terminal_state: str
    steps: tuple[StepReading, ...]
    active_step_name: str | None
    chain_summary: str
    recommendation: UnblockOrDrop
    reason: str


def _step_name(commitment_id, activity_by_id: dict, order: int) -> str:
    activity = activity_by_id.get(commitment_id)
    if activity is not None:
        return activity.commitment.name
    return f"step {order}"


def build_chain_reading(
    *,
    goal: Goal,
    activity_by_id: dict,
    now: datetime,
) -> ChainReading:
    """Read a sequence goal against its lever-step chain (D163, S63).

    unblock-or-drop operates on the steps the actor controls; the
    influence-gated terminal (the employer's decision) is represented as a state
    only. The active step is the earliest step not done and not dropped; the
    recommendation reads its state (a blocked active step → intervene; a moving
    active step → continue) — the chain's shape, not a single observation, so
    the credulity flip the S62 raise rec showed cannot recur here.
    """
    steps = goal.ordered_steps
    terminal = goal.terminal
    terminal_target = terminal.target if terminal is not None else None
    terminal_state = (
        terminal.state.value if terminal is not None else TerminalState.PENDING.value
    )

    active_step = next(
        (
            s
            for s in steps
            if s.state not in (StepState.DONE, StepState.DROPPED)
        ),
        None,
    )
    step_readings = tuple(
        StepReading(
            name=_step_name(s.commitment_id, activity_by_id, s.order),
            order=s.order,
            state=s.state,
            is_active=(active_step is not None and s.order == active_step.order),
        )
        for s in steps
    )
    active_name = (
        _step_name(active_step.commitment_id, activity_by_id, active_step.order)
        if active_step is not None
        else None
    )
    done_count = sum(1 for s in steps if s.state is StepState.DONE)
    chain_summary = (
        f"{done_count} of {len(steps)} steps done; "
        + (
            f"active: {active_name} ({active_step.state.value})"
            if active_step is not None
            else "chain complete"
        )
    )

    # No active step: the chain is done/dropped — the outcome now rests on the
    # influence-gated terminal, which the actor does not control. Nothing to
    # unblock or drop.
    if active_step is None:
        if terminal_state == TerminalState.REACHED.value:
            reason = "the terminal is reached — the goal is met"
        else:
            reason = (
                "every step the actor controls is done — the terminal is the "
                "employer's decision now (influence-gated); nothing to unblock"
            )
        return ChainReading(
            goal=goal,
            terminal_target=terminal_target,
            terminal_state=terminal_state,
            steps=step_readings,
            active_step_name=None,
            chain_summary=chain_summary,
            recommendation=UnblockOrDrop.CONTINUE,
            reason=reason,
        )

    # A blocked active step is the clearest unblock-or-drop case: read the shape.
    if active_step.state is StepState.BLOCKED:
        return ChainReading(
            goal=goal,
            terminal_target=terminal_target,
            terminal_state=terminal_state,
            steps=step_readings,
            active_step_name=active_name,
            chain_summary=chain_summary,
            recommendation=UnblockOrDrop.UNBLOCK,
            reason=(
                f"'{active_name}' is blocked — unblock it (clear what is "
                f"stalling it), or drop the step if it is no longer needed"
            ),
        )

    # A ready active step: a stalled cadence (sustained, not a single
    # observation) is the unblock signal; otherwise the chain is moving.
    activity = activity_by_id.get(active_step.commitment_id)
    if activity is not None and not _cadence_on_track(activity, now=now):
        overshoot = overdue_by_days(
            last_activity_at=(
                activity.last_completed_at or activity.commitment.created_at
            ),
            expected_interval_days=activity.commitment.expected_interval_days,
            now=now,
        )
        return ChainReading(
            goal=goal,
            terminal_target=terminal_target,
            terminal_state=terminal_state,
            steps=step_readings,
            active_step_name=active_name,
            chain_summary=chain_summary,
            recommendation=UnblockOrDrop.UNBLOCK,
            reason=(
                f"'{active_name}' has stalled — {overshoot} days without "
                f"progress; unblock it, or drop the step if it is no longer "
                f"needed"
            ),
        )

    return ChainReading(
        goal=goal,
        terminal_target=terminal_target,
        terminal_state=terminal_state,
        steps=step_readings,
        active_step_name=active_name,
        chain_summary=chain_summary,
        recommendation=UnblockOrDrop.CONTINUE,
        reason=f"'{active_name}' is moving — continue the chain",
    )


__all__ = [
    "ChainReading",
    "GoalReading",
    "RaiseOrHold",
    "StepReading",
    "UnblockOrDrop",
    "build_chain_reading",
    "build_goal_reading",
]
