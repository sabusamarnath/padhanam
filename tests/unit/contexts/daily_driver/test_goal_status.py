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


def _activity(
    commitment: Commitment,
    *,
    last_days_ago: int | None,
    didnt_days_ago: int | None = None,
    didnt_count: int | None = None,
) -> CommitmentActivity:
    last = None if last_days_ago is None else _NOW - timedelta(days=last_days_ago)
    didnt = (
        None
        if didnt_days_ago is None
        else (_NOW - timedelta(days=didnt_days_ago)).date()
    )
    # default the count to 1 when a reported miss date is given (a single miss)
    count = (
        didnt_count
        if didnt_count is not None
        else (1 if didnt_days_ago is not None else 0)
    )
    return CommitmentActivity(
        commitment=commitment,
        last_completed_at=last,
        last_reported_didnt=didnt,
        reported_didnt_count=count,
    )


def _homeostatic(lever_ids: tuple[UUID, ...]) -> Goal:
    return Goal(
        id=uuid4(), tenant_id=_TENANT, jurisdiction="eu-west", name="Habit goal",
        mode=GoalMode.HOMEOSTATIC, control=ControlAxis.SELF, subject=Subject.SELF,
        lever_commitment_ids=lever_ids,
    )


def _progressive(lever_id: UUID | None = None) -> Goal:
    return Goal(
        id=uuid4(), tenant_id=_TENANT, jurisdiction="eu-west", name="German",
        mode=GoalMode.PROGRESSIVE, control=ControlAxis.SELF, subject=Subject.SELF,
        lever_commitment_id=lever_id or uuid4(),
        lever_commitment_ids=(lever_id,) if lever_id else (),
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


def test_never_completed_daily_habit_reads_not_tracked() -> None:
    # D191: a lever with no completion does not fabricate "overdue" from its
    # age (created_at) — it reads not-tracked, the honest "the moat does not
    # know." (This supersedes S92's created_at-fabricated stalled.)
    c = _commitment(1)  # created 365d ago, never completed
    goal = _homeostatic((c.id,))
    assert (
        _status(goal, {c.id: _activity(c, last_days_ago=None)})
        is GoalStatus.NOT_TRACKED
    )


def test_partial_tracking_verdict_from_tracked_levers_only() -> None:
    # D191 partial-tracking rule: a goal reads not-tracked only when NO lever
    # has any completion. With one tracked and one untracked lever, the real
    # cadence verdict wins from the tracked lever; the untracked one neither
    # fabricates overdue nor drags the goal to not-tracked.
    tracked = _commitment(1)
    untracked = _commitment(1)
    goal = _homeostatic((tracked.id, untracked.id))
    activities = {
        tracked.id: _activity(tracked, last_days_ago=1),     # on rhythm
        untracked.id: _activity(untracked, last_days_ago=None),  # no data
    }
    assert _status(goal, activities) is GoalStatus.ON_TRACK


def test_all_levers_untracked_reads_not_tracked() -> None:
    a = _commitment(1)
    b = _commitment(1)
    goal = _homeostatic((a.id, b.id))
    activities = {
        a.id: _activity(a, last_days_ago=None),
        b.id: _activity(b, last_days_ago=None),
    }
    assert _status(goal, activities) is GoalStatus.NOT_TRACKED


def test_compute_lever_status_tracked_vs_untracked() -> None:
    from contexts.daily_driver.domain.goal_status import compute_lever_status

    c = _commitment(1)
    # untracked -> not_tracked
    assert (
        compute_lever_status(_activity(c, last_days_ago=None), now=_NOW, thresholds=_TH)
        is GoalStatus.NOT_TRACKED
    )
    # tracked -> its cadence verdict (4d overdue daily, K=3 -> stalled)
    assert (
        compute_lever_status(_activity(c, last_days_ago=4), now=_NOW, thresholds=_TH)
        is GoalStatus.STALLED
    )
    assert (
        compute_lever_status(_activity(c, last_days_ago=1), now=_NOW, thresholds=_TH)
        is GoalStatus.ON_TRACK
    )


# --- D192: the three-state cadence reading (did / reported-didn't / silent) -

def test_k_reported_misses_no_did_reads_stalled_with_evidence() -> None:
    # A daily lever never completed, with K=3 reported misses -> stalled WITH
    # evidence. The magnitude is the count of confirmed misses, never the silent
    # days between them (D192 — silence is not a miss).
    from contexts.daily_driver.domain.goal_status import compute_lever_status

    c = _commitment(1)
    a = _activity(c, last_days_ago=None, didnt_days_ago=0, didnt_count=3)
    assert compute_lever_status(a, now=_NOW, thresholds=_TH) is GoalStatus.STALLED


def test_one_reported_didnt_no_did_reads_behind_not_not_tracked() -> None:
    # A single reported miss (no did) is one confirmed miss -> behind, never
    # not-tracked (silence) and never on-track; it does not fabricate a stalled
    # streak from the silent beats since.
    from contexts.daily_driver.domain.goal_status import compute_lever_status

    c = _commitment(1)
    a = _activity(c, last_days_ago=None, didnt_days_ago=0, didnt_count=1)
    assert compute_lever_status(a, now=_NOW, thresholds=_TH) is GoalStatus.BEHIND


def test_did_on_rhythm_then_reported_didnt_reads_behind() -> None:
    # Completed yesterday (on rhythm by cadence), but reported a miss today ->
    # a confirmed lapse since completion overrides on-track to behind.
    from contexts.daily_driver.domain.goal_status import compute_lever_status

    c = _commitment(1)
    a = _activity(c, last_days_ago=1, didnt_days_ago=0)
    assert compute_lever_status(a, now=_NOW, thresholds=_TH) is GoalStatus.BEHIND


def test_homeostatic_goal_with_only_reported_misses_reads_stalled() -> None:
    # Goal-level: a homeostatic goal whose single lever has K reported misses
    # (no completion) reads stalled with evidence, not not-tracked.
    c = _commitment(1)
    goal = _homeostatic((c.id,))
    activities = {
        c.id: _activity(c, last_days_ago=None, didnt_days_ago=1, didnt_count=3)
    }
    assert _status(goal, activities) is GoalStatus.STALLED


def test_homeostatic_silent_lever_still_reads_not_tracked() -> None:
    # Neither a did nor a reported miss -> not-tracked (silence).
    c = _commitment(1)
    goal = _homeostatic((c.id,))
    activities = {c.id: _activity(c, last_days_ago=None, didnt_days_ago=None)}
    assert _status(goal, activities) is GoalStatus.NOT_TRACKED


# --- D192: the progressive not-tracked fix (the S96 residual) --------------

def test_progressive_untracked_practice_no_longer_reads_asleep() -> None:
    # The S96 residual: a progressive goal with recent edge activity but a
    # practice lever that has NO completion and NO reported miss no longer reads
    # asleep-from-created_at — it reads active (the fabrication is gone).
    cid = uuid4()
    goal = _progressive(cid)
    activities = {cid: _activity(_commitment(1, cid), last_days_ago=None)}
    assert (
        compute_goal_status(
            goal=goal, commitment_activities=activities,
            latest_activity_at=_NOW - timedelta(days=2), now=_NOW, thresholds=_TH,
        )
        is GoalStatus.ACTIVE
    )


def test_progressive_practice_reported_miss_reads_asleep_with_evidence() -> None:
    # But an *evidenced* lapse (a reported miss on the practice lever) still
    # reads asleep — the asleep tier now fires on evidence, not on age.
    cid = uuid4()
    goal = _progressive(cid)
    activities = {
        cid: _activity(
            _commitment(1, cid), last_days_ago=None, didnt_days_ago=1, didnt_count=3
        )
    }
    assert (
        compute_goal_status(
            goal=goal, commitment_activities=activities,
            latest_activity_at=_NOW - timedelta(days=2), now=_NOW, thresholds=_TH,
        )
        is GoalStatus.ASLEEP
    )


# --- cadence-less (progressive) -------------------------------------------

def test_progressive_active_within_window_stalled_past() -> None:
    goal = _progressive()
    # cannot be behind; active within 14d of activity
    assert _status(goal, latest=_NOW - timedelta(days=3)) is GoalStatus.ACTIVE
    assert _status(goal, latest=_NOW - timedelta(days=20)) is GoalStatus.STALLED


def test_progressive_never_reads_behind() -> None:
    # a progressive goal has no rhythm to slip: it never reads behind (only
    # active / asleep / stalled).
    goal = _progressive()
    assert _status(goal, latest=_NOW - timedelta(days=1)) is not GoalStatus.BEHIND


# --- D188: the asleep middle gear for progressive goals -------------------

def test_progressive_with_lapsed_practice_reads_asleep() -> None:
    # German: recent activity, but the daily practice commitment is lapsed
    # (10 days missed >= K=3) -> asleep, not active.
    cid = uuid4()
    goal = _progressive(cid)
    activities = {cid: _activity(_commitment(1, cid), last_days_ago=10)}
    assert (
        compute_goal_status(
            goal=goal, commitment_activities=activities,
            latest_activity_at=_NOW - timedelta(days=2), now=_NOW, thresholds=_TH,
        )
        is GoalStatus.ASLEEP
    )


def test_progressive_with_practice_on_rhythm_reads_active() -> None:
    cid = uuid4()
    goal = _progressive(cid)
    activities = {cid: _activity(_commitment(1, cid), last_days_ago=1)}  # on rhythm
    assert (
        compute_goal_status(
            goal=goal, commitment_activities=activities,
            latest_activity_at=_NOW - timedelta(days=2), now=_NOW, thresholds=_TH,
        )
        is GoalStatus.ACTIVE
    )


def test_progressive_lapsed_but_no_activity_reads_stalled_not_asleep() -> None:
    # precedence: no activity in the window wins over the lapse -> stalled.
    cid = uuid4()
    goal = _progressive(cid)
    activities = {cid: _activity(_commitment(1, cid), last_days_ago=10)}
    assert (
        compute_goal_status(
            goal=goal, commitment_activities=activities,
            latest_activity_at=_NOW - timedelta(days=30), now=_NOW, thresholds=_TH,
        )
        is GoalStatus.STALLED
    )


def test_progressive_with_no_practice_commitment_unchanged_from_s92() -> None:
    # no practice commitment provided -> active within window, stalled outside
    # (D187 behaviour preserved).
    goal = _progressive()  # lever id not in activities
    assert _status(goal, latest=_NOW - timedelta(days=2)) is GoalStatus.ACTIVE
    assert _status(goal, latest=_NOW - timedelta(days=20)) is GoalStatus.STALLED


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


# --- D189: the evidence-drawn why phrase ----------------------------------

def _verdict(goal, activities=None, latest=None):
    from contexts.daily_driver.domain.goal_status import compute_goal_verdict

    return compute_goal_verdict(
        goal=goal, commitment_activities=activities or {},
        latest_activity_at=latest, now=_NOW, thresholds=_TH,
    )


def test_why_phrases_drawn_from_evidence() -> None:
    c = _commitment(1)
    goal = _homeostatic((c.id,))
    assert _verdict(goal, {c.id: _activity(c, last_days_ago=1)}).why == "on rhythm"
    # behind: worst lever's overdue days
    assert _verdict(goal, {c.id: _activity(c, last_days_ago=3)}).why == "2d overdue"
    # cadence-less active: days since latest activity
    assert _verdict(_progressive(), latest=_NOW - timedelta(days=3)).why == "3d ago"
    # cadence-less stalled: quiet days
    assert _verdict(_progressive(), latest=_NOW - timedelta(days=20)).why == "quiet 20d"
    # asleep
    cid = uuid4()
    asleep_goal = _progressive(cid)
    assert _verdict(
        asleep_goal, {cid: _activity(_commitment(1, cid), last_days_ago=10)},
        latest=_NOW - timedelta(days=2),
    ).why == "practice paused"
    # done
    assert _verdict(_sequence(reached=True)).why == "reached"


# --------------------------------------------------------------------------
# Delta-4 precedence (D192, S97b): same-day did beats same-day reported_didnt.
#
# S97b's check-in makes a same-day (did, reported_didnt) collision reachable
# (before it, the checkin store was empty). The precedence already holds by
# construction in `_lever_verdict` via a strict `>` (`last_didnt >
# last_did.date()`). These pin both sides of that boundary so a future refactor
# flipping `>` to `>=` is caught: did-wins on the same day, reported-didn't-wins
# the day after a did.
# --------------------------------------------------------------------------

from contexts.daily_driver.domain.goal_status import compute_lever_status  # noqa: E402


def test_same_day_did_beats_same_day_reported_didnt() -> None:
    c = _commitment(interval=1)
    activity = _activity(c, last_days_ago=0, didnt_days_ago=0)  # both today
    assert (
        compute_lever_status(activity, now=_NOW, thresholds=_TH)
        == GoalStatus.ON_TRACK
    )


def test_reported_didnt_the_day_after_a_did_wins() -> None:
    c = _commitment(interval=1)
    # did yesterday, reported-didn't today — a confirmed lapse since completion.
    activity = _activity(c, last_days_ago=1, didnt_days_ago=0)
    status = compute_lever_status(activity, now=_NOW, thresholds=_TH)
    assert status != GoalStatus.ON_TRACK
    assert status in (GoalStatus.BEHIND, GoalStatus.STALLED)
