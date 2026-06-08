"""Unit tests for calendar items in the Today surface (D159).

Covers the calendar-to-domain mapping and build_today_view's calendar
source: a calendar event renders typed by domain, sorts by start time,
reuses the shared status vocabulary (upcoming -> ON_TRACK, past -> DONE),
and ranks between the BEHIND commitments and the NEEDS_YOU cases.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from contexts.daily_driver.domain.calendar_domain import (
    DEFAULT_CALENDAR_DOMAIN,
    resolve_calendar_domain,
)
from contexts.daily_driver.domain.commitment import (
    Commitment,
    CommitmentActivity,
)
from contexts.daily_driver.domain.today_item import (
    CalendarToday,
    ItemKind,
    ItemStatus,
    TodayView,
)
from contexts.daily_driver.domain.view_builder import build_today_view

_NOW = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
_DAY = date(2026, 6, 4)


def _event(
    title: str, *, hour: int, end_hour: int | None = None, domain: str = "work"
) -> CalendarToday:
    start = datetime(2026, 6, 4, hour, 0, tzinfo=timezone.utc)
    end = (
        datetime(2026, 6, 4, end_hour, 0, tzinfo=timezone.utc)
        if end_hour is not None
        else None
    )
    return CalendarToday(
        meeting_id=uuid4(),
        google_event_id=f"evt-{title}",
        title=title,
        start_at=start,
        end_at=end,
        domain=domain,
    )


def _view(**kwargs: object) -> TodayView:
    base: dict[str, object] = dict(
        open_cases=(),
        commitment_activities=(),
        day_states=(),
        now=_NOW,
        day_date=_DAY,
        calendar_events=(),
    )
    base.update(kwargs)
    return build_today_view(**base)  # type: ignore[arg-type]


# ---------------------------------------------------- calendar-to-domain
def test_resolve_calendar_domain_passes_through_known_tag() -> None:
    assert resolve_calendar_domain("personal") == "personal"
    assert resolve_calendar_domain("FAMILY") == "family"


def test_resolve_calendar_domain_falls_back_for_unknown_or_empty() -> None:
    assert resolve_calendar_domain(None) == DEFAULT_CALENDAR_DOMAIN
    assert resolve_calendar_domain("") == DEFAULT_CALENDAR_DOMAIN
    assert resolve_calendar_domain("rocketship") == DEFAULT_CALENDAR_DOMAIN


# ---------------------------------------------------- build_today_view
def test_calendar_event_renders_as_calendar_item_typed_by_domain() -> None:
    view = _view(calendar_events=(_event("Dentist", hour=16, domain="personal"),))
    item = view.items[0]
    assert item.kind is ItemKind.CALENDAR
    assert item.artefact_type == "meeting"
    assert item.target_cell == "calendar_conversation"
    assert item.domain == "personal"
    assert item.title == "Dentist"
    assert item.start_at is not None


def test_upcoming_event_is_on_track_past_event_is_done() -> None:
    upcoming = _event("Standup", hour=16)  # after _NOW (12:00)
    past = _event("Breakfast", hour=8, end_hour=9)  # ended before _NOW
    view = _view(calendar_events=(upcoming, past))
    # D175 time-scoping: the upcoming event is live today-forward; the ended
    # event moves to the history slice (the observed stream).
    live = {i.title: i for i in view.items}
    history = {i.title: i for i in view.history}
    assert live["Standup"].status is ItemStatus.ON_TRACK
    assert live["Standup"].done is False
    assert "Breakfast" not in live
    assert history["Breakfast"].status is ItemStatus.DONE
    assert history["Breakfast"].done is True


def test_calendar_items_sort_by_start_time_within_band() -> None:
    view = _view(
        calendar_events=(
            _event("Late", hour=17),
            _event("Early", hour=14),
            _event("Mid", hour=15),
        )
    )
    titles = [i.title for i in view.items if i.kind is ItemKind.CALENDAR]
    assert titles == ["Early", "Mid", "Late"]


def test_calendar_ranks_below_behind_and_above_needs_you() -> None:
    overdue = Commitment(
        id=uuid4(),
        tenant_id=uuid4(),
        jurisdiction="eu-west",
        name="Weekly review",
        expected_interval_days=7,
        authored_by_user_id="operator",
        created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    from contexts.daily_driver.domain.today_item import OpenCase

    case = OpenCase(case_id=uuid4(), title="Launch plan", created_at=_NOW)
    view = _view(
        open_cases=(case,),
        commitment_activities=(CommitmentActivity(overdue, None),),
        calendar_events=(_event("Standup", hour=16),),
    )
    kinds = [i.kind for i in view.items]
    assert kinds == [
        ItemKind.COMMITMENT,  # BEHIND
        ItemKind.CALENDAR,  # time-anchored
        ItemKind.CASE,  # NEEDS_YOU
    ]


def test_no_calendar_events_is_the_s58_view() -> None:
    view = _view()
    assert view.items == ()
