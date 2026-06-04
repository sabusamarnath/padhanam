"""build_today_view — assemble the prioritised-today list (D157).

Pure domain logic: takes the OPEN Cases, the Commitments-with-activity,
the persisted per-day states, and ``now``/``day_date``; computes each
item's status and a default priority, applies the user's persisted
ordering and done-for-today marks, and returns the ordered ``TodayView``.

Default priority (when the user has not reordered): BEHIND commitments
first (the active-surfacing signal the whole pivot rests on), then
NEEDS_YOU cases, then ON_TRACK commitments; done-for-today items sink to
the bottom regardless. A persisted ``position`` overrides the default
rank for that item.

``now`` is injected by the application layer; the domain stays pure and
deterministic per D16.
"""

from __future__ import annotations

from datetime import date, datetime

from contexts.daily_driver.domain.commitment import CommitmentActivity
from contexts.daily_driver.domain.day import DayItemState, item_key
from contexts.daily_driver.domain.staleness import is_overdue, overdue_by_days
from contexts.daily_driver.domain.today_item import (
    ItemKind,
    ItemStatus,
    OpenCase,
    TodayItem,
    TodayView,
)

# Default rank by computed status (lower sorts first). Done items are
# pushed below everything via a separate leading sort key, so DONE is
# not ranked here.
_STATUS_RANK: dict[ItemStatus, int] = {
    ItemStatus.BEHIND: 0,
    ItemStatus.NEEDS_YOU: 1,
    ItemStatus.ON_TRACK: 2,
}

_CASE_CELL = "mirror_conversation"
_COMMITMENT_CELL = "commitment_detail"


def _case_item(case: OpenCase, state: DayItemState | None) -> TodayItem:
    done = state.done if state is not None else False
    position = state.position if state is not None else None
    return TodayItem(
        kind=ItemKind.CASE,
        item_id=case.case_id,
        title=case.title,
        status=ItemStatus.DONE if done else ItemStatus.NEEDS_YOU,
        target_cell=_CASE_CELL,
        artefact_type="case",
        detail="open — needs you",
        position=position,
        done=done,
        overdue_by_days=None,
    )


def _commitment_item(
    activity: CommitmentActivity,
    state: DayItemState | None,
    *,
    now: datetime,
) -> TodayItem:
    commitment = activity.commitment
    last_activity = activity.last_completed_at or commitment.created_at
    overdue = is_overdue(
        last_activity_at=last_activity,
        expected_interval_days=commitment.expected_interval_days,
        now=now,
    )
    overshoot = (
        overdue_by_days(
            last_activity_at=last_activity,
            expected_interval_days=commitment.expected_interval_days,
            now=now,
        )
        if overdue
        else None
    )
    done = state.done if state is not None else False
    position = state.position if state is not None else None
    if done:
        status = ItemStatus.DONE
        detail = "done for today"
    elif overdue:
        status = ItemStatus.BEHIND
        plural = "s" if overshoot != 1 else ""
        detail = f"behind on this — {overshoot} day{plural} over"
    else:
        status = ItemStatus.ON_TRACK
        detail = f"every {commitment.expected_interval_days} days"
    return TodayItem(
        kind=ItemKind.COMMITMENT,
        item_id=commitment.id,
        title=commitment.name,
        status=status,
        target_cell=_COMMITMENT_CELL,
        artefact_type="commitment",
        detail=detail,
        position=position,
        done=done,
        overdue_by_days=overshoot,
    )


def _status_for_rank(item: TodayItem) -> ItemStatus:
    """The status used for default ranking (DONE is handled separately)."""
    if item.done:
        if item.kind is ItemKind.CASE:
            return ItemStatus.NEEDS_YOU
        if item.overdue_by_days is not None:
            return ItemStatus.BEHIND
        return ItemStatus.ON_TRACK
    return item.status


def _sort_key(item: TodayItem) -> tuple[int, int, str]:
    done_key = 1 if item.done else 0
    if item.position is not None:
        order_key = item.position
    else:
        order_key = 1000 + _STATUS_RANK[_status_for_rank(item)]
    return (done_key, order_key, item.title.lower())


def build_today_view(
    *,
    open_cases: tuple[OpenCase, ...],
    commitment_activities: tuple[CommitmentActivity, ...],
    day_states: tuple[DayItemState, ...],
    now: datetime,
    day_date: date,
) -> TodayView:
    """Compose the ordered prioritised-today list (D157)."""
    states_by_key = {
        item_key(state.kind, state.item_id): state for state in day_states
    }
    items: list[TodayItem] = []
    for case in open_cases:
        state = states_by_key.get(item_key(ItemKind.CASE, case.case_id))
        items.append(_case_item(case, state))
    for activity in commitment_activities:
        state = states_by_key.get(
            item_key(ItemKind.COMMITMENT, activity.commitment.id)
        )
        items.append(_commitment_item(activity, state, now=now))
    items.sort(key=_sort_key)
    return TodayView(day_date=day_date, items=tuple(items))


__all__ = ["build_today_view"]
