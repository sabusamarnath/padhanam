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

from contexts.daily_driver.domain.commitment import (
    CommitmentActivity,
    OutcomeStatus,
)
from contexts.daily_driver.domain.day import DayItemState, item_key
from contexts.daily_driver.domain.staleness import (
    is_drop_candidate,
    is_overdue,
    overdue_by_days,
)
from contexts.daily_driver.domain.today_item import (
    CalendarToday,
    ItemKind,
    ItemStatus,
    OpenCase,
    TodayItem,
    TodayView,
)

# Default rank band (lower sorts first), computed per item from kind +
# status. Done items are pushed below everything via a separate leading
# sort key. BEHIND commitments lead (the active-surfacing signal); a
# calendar item is time-anchored and sits just below, above the
# pull-when-ready Cases (NEEDS_YOU) and the steady ON_TRACK commitments.
_RANK_BEHIND = 0
_RANK_CALENDAR = 1
_RANK_NEEDS_YOU = 2
_RANK_ON_TRACK = 3

_CASE_CELL = "mirror_conversation"
_COMMITMENT_CELL = "commitment_detail"
_CALENDAR_CELL = "calendar_conversation"

# Cases and Commitments are the work domain at Phase 2-A (the portfolio is
# professional); a calendar item inherits its connection's tag (D159).
_WORK_DOMAIN = "work"


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
        domain=_WORK_DOMAIN,
    )


def _calendar_item(event: CalendarToday, *, now: datetime) -> TodayItem:
    """Build a read-through calendar today-item (D159).

    A calendar event carries no ``DayItemState`` — it is an external-source
    fact, not a user-authored item, so it is not a reorder or done target
    this slice (position ``None``). Status reuses the shared vocabulary: an
    event whose end has passed is ``DONE``; one upcoming or in progress is
    ``ON_TRACK``. The human time rides ``detail``; the structured start
    drives time-ordering and the drawer's When field.
    """
    ended = event.end_at is not None and event.end_at <= now
    in_progress = (
        event.start_at is not None
        and event.start_at <= now
        and (event.end_at is None or now < event.end_at)
    )
    status = ItemStatus.DONE if ended else ItemStatus.ON_TRACK
    detail = _calendar_detail(event, now=now, in_progress=in_progress)
    return TodayItem(
        kind=ItemKind.CALENDAR,
        item_id=event.meeting_id,
        title=event.title,
        status=status,
        target_cell=_CALENDAR_CELL,
        artefact_type="meeting",
        detail=detail,
        position=None,
        done=ended,
        overdue_by_days=None,
        domain=event.domain,
        start_at=event.start_at,
    )


def _calendar_detail(
    event: CalendarToday, *, now: datetime, in_progress: bool
) -> str:
    if event.start_at is None:
        return "today"
    when = event.start_at.strftime("%H:%M")
    if in_progress:
        return f"now · started {when}"
    if event.end_at is not None and event.end_at <= now:
        return f"earlier · {when}"
    return f"today · {when}"


def _last_progress_at(activity: CommitmentActivity) -> datetime:
    """The most recent real update point for a Commitment (D162).

    Composed at render from creation, last completion, and the
    observation-capture timestamp — no persisted ``last_progress_at``
    column. This is the signal the drop-candidate query reads.
    """
    commitment = activity.commitment
    candidates = [commitment.created_at]
    if activity.last_completed_at is not None:
        candidates.append(activity.last_completed_at)
    if commitment.observed_at is not None:
        candidates.append(commitment.observed_at)
    return max(candidates)


def _commitment_item(
    activity: CommitmentActivity,
    state: DayItemState | None,
    *,
    now: datetime,
    drop_candidate_quiet_days: int | None,
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
    # Drop candidacy is independent of (and a longer window than) BEHIND:
    # open, not already dropped, and quiet past the configured threshold.
    # A recommendation only — the operator acts, the platform never drops.
    dropped = commitment.outcome_status is OutcomeStatus.DROPPED
    drop_candidate = (
        drop_candidate_quiet_days is not None
        and not done
        and not dropped
        and is_drop_candidate(
            last_progress_at=_last_progress_at(activity),
            quiet_days_threshold=drop_candidate_quiet_days,
            now=now,
        )
    )
    outcome_status = (
        commitment.outcome_status.value
        if commitment.outcome_status is not None
        else None
    )
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
        domain=_WORK_DOMAIN,
        expected_outcome=commitment.expected_outcome,
        observed_outcome=commitment.observed_outcome,
        outcome_status=outcome_status,
        drop_candidate=drop_candidate,
    )


def _default_rank(item: TodayItem) -> int:
    """Default rank band for an item (lower sorts first; DONE handled separately).

    Uses kind + status so a calendar item ranks by its own band rather
    than borrowing a commitment's status meaning. For a done item the rank
    is its underlying (not-done) band, so done items keep a stable order
    among themselves once sunk to the bottom.
    """
    if item.kind is ItemKind.CALENDAR:
        return _RANK_CALENDAR
    if item.kind is ItemKind.CASE:
        return _RANK_NEEDS_YOU
    # Commitment: BEHIND leads, else ON_TRACK.
    if item.overdue_by_days is not None or item.status is ItemStatus.BEHIND:
        return _RANK_BEHIND
    return _RANK_ON_TRACK


def _tiebreak(item: TodayItem) -> str:
    """Within a rank band: calendar items by start time, others by title."""
    if item.kind is ItemKind.CALENDAR and item.start_at is not None:
        return item.start_at.isoformat()
    return item.title.lower()


def _sort_key(item: TodayItem) -> tuple[int, int, str]:
    done_key = 1 if item.done else 0
    if item.position is not None:
        order_key = item.position
    else:
        order_key = 1000 + _default_rank(item)
    return (done_key, order_key, _tiebreak(item))


def build_today_view(
    *,
    open_cases: tuple[OpenCase, ...],
    commitment_activities: tuple[CommitmentActivity, ...],
    day_states: tuple[DayItemState, ...],
    now: datetime,
    day_date: date,
    calendar_events: tuple[CalendarToday, ...] = (),
    drop_candidate_quiet_days: int | None = None,
) -> TodayView:
    """Compose the ordered prioritised-today list (D157, D159, D162).

    Three item sources render in one list typed by domain: OPEN Cases,
    Commitments-with-activity, and today's calendar events. Calendar items
    are read-through (no ``DayItemState``); Cases and Commitments carry the
    user's persisted ordering and done marks.

    ``drop_candidate_quiet_days`` (D162) is the configured quiet-window
    threshold: an open, not-yet-dropped Commitment with no progress for at
    least that many days is flagged ``drop_candidate`` (a recommendation,
    never an auto-drop). ``None`` disables flagging — the surface degrades
    to the S60 view rather than guessing a threshold.
    """
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
        items.append(
            _commitment_item(
                activity,
                state,
                now=now,
                drop_candidate_quiet_days=drop_candidate_quiet_days,
            )
        )
    for event in calendar_events:
        items.append(_calendar_item(event, now=now))
    items.sort(key=_sort_key)
    # Time-scope to today-forward (D173/D175): completed/ended items leave the
    # live plan for the history slice (the observed stream feeding D162). Kept,
    # not deleted — an item's done mark is observation data the loop needs.
    live = tuple(item for item in items if not item.done)
    history = tuple(item for item in items if item.done)
    return TodayView(day_date=day_date, items=live, history=history)


__all__ = ["build_today_view"]
