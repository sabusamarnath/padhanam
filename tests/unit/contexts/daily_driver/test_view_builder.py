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


def _commitment(name: str, interval: int, created_day: int) -> Commitment:
    return Commitment(
        id=uuid4(),
        tenant_id=uuid4(),
        jurisdiction="eu-west",
        name=name,
        expected_interval_days=interval,
        authored_by_user_id="operator",
        created_at=datetime(2026, 5, created_day, tzinfo=timezone.utc),
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


def test_done_mark_overlays_and_sinks_to_bottom() -> None:
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
    assert view.items[-1].status == ItemStatus.DONE
    assert view.items[-1].done is True
    # the non-done case ranks above the done (formerly-behind) commitment
    assert view.items[0].kind == ItemKind.CASE


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
