"""Shared fixtures for calendar-conversation unit tests (S55b-1)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from contexts.calendar.domain.meeting import Meeting, MeetingAttendee, MeetingStatus

_TENANT = UUID("00000000-0000-4000-8000-00000000a001")


def make_meeting(
    *,
    title: str,
    start_at: datetime | None,
    attendees: tuple[str, ...] = (),
    organizer_email: str | None = None,
    status: MeetingStatus = MeetingStatus.CONFIRMED,
    event_id: str | None = None,
    now: datetime | None = None,
) -> Meeting:
    now = now or datetime(2026, 6, 2, 9, 0, tzinfo=timezone.utc)
    return Meeting(
        id=uuid4(),
        tenant_id=_TENANT,
        jurisdiction="eu-west",
        google_event_id=event_id or uuid4().hex,
        status=status,
        title=title,
        description=None,
        location=None,
        attendees=tuple(
            MeetingAttendee(email=a, display_name=a, response_status="accepted")
            for a in attendees
        ),
        organizer_email=organizer_email,
        start_at=start_at,
        end_at=None,
        start_raw=start_at.isoformat() if start_at else None,
        end_raw=None,
        source_updated_at=None,
        recurring_event_id=None,
        html_link=None,
        content_hash="h" if status is not MeetingStatus.CANCELLED else None,
        created_at=now,
        updated_at=now,
    )
