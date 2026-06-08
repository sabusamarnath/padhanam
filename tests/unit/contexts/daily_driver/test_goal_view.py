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


# --- sequence reading: unblock-or-drop (S63, D163) ------------------------

from contexts.daily_driver.domain.goal import (  # noqa: E402
    ControlAxis,
    GoalMode,
    LeverStep,
    StepState,
    Subject,
    Terminal,
    TerminalState,
)
from contexts.daily_driver.domain.goal_view import (  # noqa: E402
    ChainReading,
    UnblockOrDrop,
    build_chain_reading,
)

_SEQ_OUTCOME = UUID("00000000-0000-4000-8000-0000006300a1")
_C1 = UUID("00000000-0000-4000-8000-0000006300c1")
_C2 = UUID("00000000-0000-4000-8000-0000006300c2")
_C3 = UUID("00000000-0000-4000-8000-0000006300c3")


def _seq_goal(states) -> Goal:
    return Goal(
        id=_SEQ_OUTCOME,
        tenant_id=UUID("00000000-0000-4000-8000-00000000d001"),
        jurisdiction="eu-west",
        name="Get a job",
        mode=GoalMode.SEQUENCE,
        control=ControlAxis.OTHER,
        subject=Subject.SELF,
        terminal=Terminal(target="Offer accepted", state=TerminalState.PENDING),
        steps=tuple(
            LeverStep(commitment_id=cid, order=i + 1, state=st)
            for i, (cid, st) in enumerate(states)
        ),
    )


def test_chain_blocked_active_step_recommends_unblock() -> None:
    goal = _seq_goal(
        [(_C1, StepState.DONE), (_C2, StepState.BLOCKED), (_C3, StepState.BLOCKED)]
    )
    reading = build_chain_reading(goal=goal, activity_by_id={}, now=_NOW)
    assert isinstance(reading, ChainReading)
    assert reading.recommendation is UnblockOrDrop.UNBLOCK
    assert "drop" in reading.reason  # both interventions offered
    assert reading.active_step_name is not None
    active = [s for s in reading.steps if s.is_active]
    assert len(active) == 1 and active[0].order == 2


def test_chain_complete_awaits_influence_gated_terminal() -> None:
    goal = _seq_goal(
        [(_C1, StepState.DONE), (_C2, StepState.DONE), (_C3, StepState.DONE)]
    )
    reading = build_chain_reading(goal=goal, activity_by_id={}, now=_NOW)
    assert reading.recommendation is UnblockOrDrop.CONTINUE
    assert reading.terminal_state == "pending"
    assert reading.active_step_name is None


def test_chain_ready_active_step_on_track_continues() -> None:
    goal = _seq_goal(
        [(_C1, StepState.DONE), (_C2, StepState.READY), (_C3, StepState.BLOCKED)]
    )
    # active step (C2) has a fresh, on-track lever → continue, not unblock.
    activity = CommitmentActivity(
        commitment=Commitment(
            id=_C2,
            tenant_id=UUID("00000000-0000-4000-8000-00000000d001"),
            jurisdiction="eu-west",
            name="Apply to target roles",
            expected_interval_days=7,
            authored_by_user_id="operator-001",
            created_at=_NOW - timedelta(days=1),
        ),
        last_completed_at=_NOW - timedelta(hours=2),
    )
    reading = build_chain_reading(
        goal=goal, activity_by_id={_C2: activity}, now=_NOW
    )
    assert reading.recommendation is UnblockOrDrop.CONTINUE
