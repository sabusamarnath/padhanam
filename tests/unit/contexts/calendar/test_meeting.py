"""Unit tests for the Meeting domain and CalendarEvent->Meeting mapping (D148)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contexts.calendar.domain.calendar_event import (
    CalendarEvent,
    CalendarEventStatus,
    EventAttendee,
)
from contexts.calendar.domain.meeting import (
    Meeting,
    MeetingAttendee,
    MeetingStatus,
    meeting_from_event,
    synthesise_meeting_text,
)

_NOW = datetime(2026, 5, 28, 12, 0, 0, tzinfo=timezone.utc)


def _event(**overrides: object) -> CalendarEvent:
    base: dict[str, object] = {
        "google_event_id": "evt-1",
        "status": CalendarEventStatus.CONFIRMED,
        "summary": "Board sync",
        "description": "Quarterly review",
        "location": "Room 4",
        "start": "2026-05-12T09:00:00+01:00",
        "end": "2026-05-12T10:00:00+01:00",
        "attendees": (
            EventAttendee(
                email="ada@example.com",
                display_name="Ada",
                response_status="accepted",
                organizer=False,
            ),
        ),
        "organizer_email": "chair@example.com",
        "updated": "2026-05-01T08:00:00Z",
        "html_link": "https://calendar.google.com/evt-1",
        "recurring_event_id": None,
    }
    base.update(overrides)
    return CalendarEvent(**base)  # type: ignore[arg-type]


def test_meeting_from_event_maps_fields_and_parses_start() -> None:
    meeting = meeting_from_event(
        _event(),
        tenant_id=uuid4(),
        jurisdiction="eu-west",
        meeting_id=uuid4(),
        now=_NOW,
    )
    assert meeting.google_event_id == "evt-1"
    assert meeting.status is MeetingStatus.CONFIRMED
    assert meeting.title == "Board sync"
    assert meeting.organizer_email == "chair@example.com"
    assert meeting.attendees[0].display_name == "Ada"
    # Start parsed to an aware datetime; raw value preserved.
    assert meeting.start_at == datetime(
        2026, 5, 12, 9, 0, tzinfo=timezone(__import__("datetime").timedelta(hours=1))
    )
    assert meeting.start_raw == "2026-05-12T09:00:00+01:00"
    assert meeting.content_hash is not None


def test_content_hash_changes_with_content() -> None:
    base = meeting_from_event(
        _event(), tenant_id=uuid4(), jurisdiction="eu", meeting_id=uuid4(), now=_NOW
    )
    changed = meeting_from_event(
        _event(summary="Board sync RESCHEDULED"),
        tenant_id=uuid4(),
        jurisdiction="eu",
        meeting_id=uuid4(),
        now=_NOW,
    )
    assert base.content_hash != changed.content_hash


def test_synthesise_text_is_deterministic_and_includes_fields() -> None:
    text = synthesise_meeting_text(
        title="T",
        description="D",
        location="L",
        attendees=(MeetingAttendee("a@x.com", "Ada", None),),
        organizer_email="o@x.com",
    )
    assert "Title: T" in text
    assert "Attendees: Ada" in text
    assert "Organizer: o@x.com" in text
    # Deterministic field order -> stable hash input.
    again = synthesise_meeting_text(
        title="T",
        description="D",
        location="L",
        attendees=(MeetingAttendee("a@x.com", "Ada", None),),
        organizer_email="o@x.com",
    )
    assert text == again


def test_all_day_date_parses_and_missing_start_is_none() -> None:
    meeting = meeting_from_event(
        _event(start="2026-06-01", end="2026-06-02"),
        tenant_id=uuid4(),
        jurisdiction="eu",
        meeting_id=uuid4(),
        now=_NOW,
    )
    assert meeting.start_at == datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
    no_start = meeting_from_event(
        _event(start=None),
        tenant_id=uuid4(),
        jurisdiction="eu",
        meeting_id=uuid4(),
        now=_NOW,
    )
    assert no_start.start_at is None


def test_meeting_rejects_empty_event_id() -> None:
    with pytest.raises(ValueError):
        Meeting(
            id=uuid4(),
            tenant_id=uuid4(),
            jurisdiction="eu",
            google_event_id="",
            status=MeetingStatus.CONFIRMED,
            title=None,
            description=None,
            location=None,
            attendees=(),
            organizer_email=None,
            start_at=None,
            end_at=None,
            start_raw=None,
            end_raw=None,
            source_updated_at=None,
            recurring_event_id=None,
            html_link=None,
            content_hash=None,
            created_at=_NOW,
            updated_at=_NOW,
        )
