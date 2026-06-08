"""Unit tests for build_today_view — status, priority, ordering (D157).

The felt-differentiator assertion lives here: an overdue Commitment is
computed BEHIND and sorts to the top of the prioritised list.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from contexts.daily_driver.domain.commitment import (
    Commitment,
    CommitmentActivity,
    OutcomeStatus,
)
from contexts.daily_driver.domain.day import DayItemState
from contexts.daily_driver.domain.today_item import (
    ItemKind,
    ItemStatus,
    OpenCase,
    TodayView,
)
from contexts.daily_driver.domain.view_builder import build_today_view

_NOW = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
_DAY = date(2026, 6, 4)


def _commitment(name: str, interval: int, created_day: int, **kw: object) -> Commitment:
    return Commitment(
        id=uuid4(),
        tenant_id=uuid4(),
        jurisdiction="eu-west",
        name=name,
        expected_interval_days=interval,
        authored_by_user_id="operator",
        created_at=datetime(2026, 5, created_day, tzinfo=timezone.utc),
        **kw,  # type: ignore[arg-type]
    )


def _view(**kwargs: object) -> TodayView:
    base: dict[str, object] = dict(
        open_cases=(),
        commitment_activities=(),
        day_states=(),
        now=_NOW,
        day_date=_DAY,
    )
    base.update(kwargs)
    return build_today_view(**base)  # type: ignore[arg-type]


def test_overdue_commitment_is_behind_and_sorts_first() -> None:
    overdue = _commitment("Weekly review", interval=7, created_day=1)  # >7d ago
    on_track = CommitmentActivity(
        commitment=Commitment(
            id=uuid4(),
            tenant_id=uuid4(),
            jurisdiction="eu-west",
            name="Daily standup",
            expected_interval_days=1,
            authored_by_user_id="operator",
            created_at=_NOW,
        ),
        last_completed_at=_NOW,
    )
    case = OpenCase(case_id=uuid4(), title="Launch plan", created_at=_NOW)
    view = _view(
        open_cases=(case,),
        commitment_activities=(CommitmentActivity(overdue, None), on_track),
    )
    statuses = [i.status for i in view.items]
    assert view.items[0].status == ItemStatus.BEHIND
    assert view.items[0].overdue_by_days is not None
    assert ItemStatus.NEEDS_YOU in statuses
    assert ItemStatus.ON_TRACK in statuses
    # default priority: BEHIND, then NEEDS_YOU (case), then ON_TRACK
    assert [i.status for i in view.items] == [
        ItemStatus.BEHIND,
        ItemStatus.NEEDS_YOU,
        ItemStatus.ON_TRACK,
    ]


def test_last_completion_clears_overdue() -> None:
    c = _commitment("Weekly review", interval=7, created_day=1)
    view = _view(
        commitment_activities=(CommitmentActivity(c, last_completed_at=_NOW),),
    )
    assert view.items[0].status == ItemStatus.ON_TRACK


def test_done_item_moves_to_history_not_the_live_list() -> None:
    # D175 time-scoping: a done item leaves the live today-forward list for the
    # history slice (the observed stream feeding D162) — kept, not deleted.
    overdue = _commitment("Weekly review", interval=7, created_day=1)
    case = OpenCase(case_id=uuid4(), title="Launch plan", created_at=_NOW)
    done_state = DayItemState(
        kind=ItemKind.COMMITMENT, item_id=overdue.id, position=None, done=True
    )
    view = _view(
        open_cases=(case,),
        commitment_activities=(CommitmentActivity(overdue, None),),
        day_states=(done_state,),
    )
    # The done commitment is in history, not the live list.
    assert view.history[-1].status == ItemStatus.DONE
    assert view.history[-1].done is True
    assert overdue.id not in {i.item_id for i in view.items}
    # The live list is today-forward: the not-done case remains.
    assert view.items[0].kind == ItemKind.CASE
    assert all(i.done is False for i in view.items)


# --- S61 (D162): the gap view + drop-candidate recommendation ------


def test_outcome_fields_surface_on_the_commitment_row() -> None:
    c = _commitment(
        "Mentor Priya",
        interval=7,
        created_day=1,
        expected_outcome="she leads the migration",
        observed_outcome="she led it well",
        outcome_status=OutcomeStatus.MET,
        observed_at=_NOW,
    )
    view = _view(commitment_activities=(CommitmentActivity(c, _NOW),))
    item = view.items[0]
    assert item.expected_outcome == "she leads the migration"
    assert item.observed_outcome == "she led it well"
    assert item.outcome_status == "met"


def test_drop_candidate_flagged_when_quiet_past_threshold() -> None:
    # created 2026-05-01, now 2026-06-04 → 34 days quiet; N=21 → candidate.
    quiet = _commitment("Old habit", interval=7, created_day=1)
    view = _view(
        commitment_activities=(CommitmentActivity(quiet, None),),
        drop_candidate_quiet_days=21,
    )
    assert view.items[0].drop_candidate is True


def test_drop_candidate_not_flagged_when_threshold_unset() -> None:
    quiet = _commitment("Old habit", interval=7, created_day=1)
    view = _view(commitment_activities=(CommitmentActivity(quiet, None),))
    assert view.items[0].drop_candidate is False


def test_drop_candidate_not_flagged_within_threshold() -> None:
    # created 2026-06-01, now 2026-06-04 → 3 days quiet; N=21 → not yet.
    fresh = Commitment(
        id=uuid4(),
        tenant_id=uuid4(),
        jurisdiction="eu-west",
        name="New habit",
        expected_interval_days=7,
        authored_by_user_id="operator",
        created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    view = _view(
        commitment_activities=(CommitmentActivity(fresh, None),),
        drop_candidate_quiet_days=21,
    )
    assert view.items[0].drop_candidate is False


def test_recent_observation_resets_the_quiet_window() -> None:
    # created long ago, but an observation recorded today → not quiet.
    observed = _commitment(
        "Re-engaged",
        interval=7,
        created_day=1,
        observed_outcome="checked in",
        outcome_status=OutcomeStatus.PARTIAL,
        observed_at=_NOW,
    )
    view = _view(
        commitment_activities=(CommitmentActivity(observed, None),),
        drop_candidate_quiet_days=21,
    )
    assert view.items[0].drop_candidate is False


def test_dropped_commitment_is_not_a_drop_candidate() -> None:
    dropped = _commitment(
        "Let go", interval=7, created_day=1, outcome_status=OutcomeStatus.DROPPED
    )
    view = _view(
        commitment_activities=(CommitmentActivity(dropped, None),),
        drop_candidate_quiet_days=21,
    )
    assert view.items[0].drop_candidate is False
    assert view.items[0].outcome_status == "dropped"


def test_done_commitment_is_not_a_drop_candidate() -> None:
    quiet = _commitment("Old habit", interval=7, created_day=1)
    done_state = DayItemState(
        kind=ItemKind.COMMITMENT, item_id=quiet.id, position=None, done=True
    )
    view = _view(
        commitment_activities=(CommitmentActivity(quiet, None),),
        day_states=(done_state,),
        drop_candidate_quiet_days=21,
    )
    # The done commitment is in history (D175); it is not a drop candidate.
    assert view.history[0].drop_candidate is False
    assert not view.items


def test_persisted_position_overrides_default_rank() -> None:
    overdue = _commitment("Weekly review", interval=7, created_day=1)
    case = OpenCase(case_id=uuid4(), title="Launch plan", created_at=_NOW)
    # user pins the case to position 0, the behind commitment to 1
    states = (
        DayItemState(kind=ItemKind.CASE, item_id=case.case_id, position=0, done=False),
        DayItemState(kind=ItemKind.COMMITMENT, item_id=overdue.id, position=1, done=False),
    )
    view = _view(
        open_cases=(case,),
        commitment_activities=(CommitmentActivity(overdue, None),),
        day_states=states,
    )
    assert view.items[0].kind == ItemKind.CASE
    assert view.items[1].kind == ItemKind.COMMITMENT
