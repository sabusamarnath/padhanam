"""Shared fixtures for threshold-briefing unit tests (S57)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from contexts.threshold_briefing.domain.meeting_state import MeetingState


def make_meeting(
    *,
    title: str,
    status: str = "confirmed",
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    cancelled_at: datetime | None = None,
    google_event_id: str | None = None,
) -> MeetingState:
    return MeetingState(
        google_event_id=google_event_id or uuid4().hex,
        meeting_id=uuid4(),
        title=title,
        status=status,
        start_at=start_at,
        end_at=end_at,
        cancelled_at=cancelled_at,
    )


def at(hour: int, *, day: int = 3) -> datetime:
    """A UTC instant on 2026-06-{day} at the given hour (test convenience)."""
    return datetime(2026, 6, day, hour, 0, tzinfo=timezone.utc)
