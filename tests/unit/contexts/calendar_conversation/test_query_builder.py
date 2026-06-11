"""Unit tests for the calendar-conversation query builder (D148, S55b-1)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from contexts.calendar_conversation.application.query_builder import (
    meetings_in_window,
    meetings_with_attendee,
    next_meeting,
    resolve_title_reference,
    resolve_window,
)
from tests.unit.contexts.calendar_conversation.conftest import make_meeting

# Tuesday 2026-06-02 12:00 UTC (weekday()==1).
_NOW = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)


def test_resolve_window_today_and_tomorrow() -> None:
    start, end = resolve_window("today", now=_NOW)
    assert start == datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc)
    start, end = resolve_window("tomorrow", now=_NOW)
    assert start == datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc)


def test_resolve_window_this_week_starts_monday() -> None:
    start, end = resolve_window("this_week", now=_NOW)
    assert start == datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)  # Monday
    assert end == datetime(2026, 6, 8, 0, 0, tzinfo=timezone.utc)


def test_resolve_window_unknown_raises() -> None:
    with pytest.raises(ValueError):
        resolve_window("someday", now=_NOW)


def test_meetings_in_window_filters_and_sorts() -> None:
    m_today = make_meeting(title="A", start_at=datetime(2026, 6, 2, 15, 0, tzinfo=timezone.utc))
    m_early = make_meeting(title="B", start_at=datetime(2026, 6, 2, 9, 0, tzinfo=timezone.utc))
    m_next_week = make_meeting(title="C", start_at=datetime(2026, 6, 10, 9, 0, tzinfo=timezone.utc))
    start, end = resolve_window("today", now=_NOW)
    got = meetings_in_window((m_today, m_early, m_next_week), start=start, end=end)
    assert [m.title for m in got] == ["B", "A"]  # soonest first


def test_meetings_with_attendee_substring_case_insensitive() -> None:
    m1 = make_meeting(title="A", start_at=_NOW, attendees=("ada@x.com",))
    m2 = make_meeting(title="B", start_at=_NOW, attendees=("bob@x.com",))
    got = meetings_with_attendee((m1, m2), attendee="ADA")
    assert {m.title for m in got} == {"A"}


def test_next_meeting_skips_past_and_cancelled() -> None:
    from contexts.calendar.domain.meeting import MeetingStatus

    past = make_meeting(title="past", start_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc))
    soon = make_meeting(title="soon", start_at=datetime(2026, 6, 2, 15, 0, tzinfo=timezone.utc))
    later = make_meeting(title="later", start_at=datetime(2026, 6, 3, 9, 0, tzinfo=timezone.utc))
    got = next_meeting((past, later, soon), now=_NOW)
    assert got is not None and got.title == "soon"


def test_resolve_title_single_multi_none() -> None:
    a = make_meeting(title="Board sync", start_at=_NOW)
    b = make_meeting(title="Board sync", start_at=_NOW)
    c = make_meeting(title="Standup", start_at=_NOW)
    # Single best match.
    matched, candidates = resolve_title_reference("standup", (a, b, c))
    assert matched is c and candidates == ()
    # Multi-match tie -> candidates.
    matched, candidates = resolve_title_reference("board sync", (a, b, c))
    assert matched is None and len(candidates) == 2
    # No match.
    matched, candidates = resolve_title_reference("budget review", (a, b, c))
    assert matched is None and candidates == ()


def test_resolve_title_folds_recurring_series_to_one() -> None:
    # A recurring event's many same-titled instances share a recurring_event_id;
    # the fold (D175) collapses them to one representative so opening it renders
    # directly instead of forcing a "choose among N" clarification (the web-path
    # 500 root cause: the clarification's pending has no real originating intake).
    series = [
        make_meeting(
            title="Second dose", start_at=_NOW, recurring_event_id="rec-1"
        )
        for _ in range(120)
    ]
    other = make_meeting(title="Standup", start_at=_NOW)
    matched, candidates = resolve_title_reference(
        "second dose", (*series, other)
    )
    assert matched is not None and matched.recurring_event_id == "rec-1"
    assert candidates == ()


def test_resolve_title_distinct_series_still_clarify() -> None:
    # Two *distinct* recurring series sharing a title fold to one each, so the
    # clarification is among series (2), not raw instances — manageable, honest.
    s1 = [
        make_meeting(title="Sync", start_at=_NOW, recurring_event_id="a")
        for _ in range(5)
    ]
    s2 = [
        make_meeting(title="Sync", start_at=_NOW, recurring_event_id="b")
        for _ in range(5)
    ]
    matched, candidates = resolve_title_reference("sync", (*s1, *s2))
    assert matched is None and len(candidates) == 2
