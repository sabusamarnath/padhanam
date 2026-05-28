"""CalendarEvent — provider-neutral domain shape for a fetched event (D148).

What the calendar source returns, mapped off the vendor wire format by
the adapter into a framework-free domain value object. Distinct from the
stored ``Meeting`` artefact: a CalendarEvent is the wire-to-domain DTO
(including cancelled tombstones that carry only id + status), while a
Meeting is the persisted, encrypted, indexed artefact the pipeline mints
from a CalendarEvent plus tenant context.

Start/end are kept as the raw RFC3339 string (timed ``dateTime``) or
date string (all-day ``date``) exactly as the source returned them; the
CalendarEvent→Meeting mapping is where a best-effort ``start_at`` parse
happens. No vendor types appear here (no-vendor-SDK-in-domain).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class CalendarEventStatus(StrEnum):
    """Google event lifecycle status; ``CANCELLED`` is the tombstone."""

    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class EventAttendee:
    email: str | None
    display_name: str | None
    response_status: str | None
    organizer: bool = False


@dataclass(frozen=True)
class CalendarEvent:
    google_event_id: str
    status: CalendarEventStatus
    summary: str | None = None
    description: str | None = None
    location: str | None = None
    start: str | None = None
    end: str | None = None
    attendees: tuple[EventAttendee, ...] = field(default_factory=tuple)
    organizer_email: str | None = None
    updated: str | None = None
    html_link: str | None = None
    recurring_event_id: str | None = None

    def __post_init__(self) -> None:
        if not self.google_event_id or not self.google_event_id.strip():
            raise ValueError("CalendarEvent.google_event_id must be non-empty")

    @property
    def is_tombstone(self) -> bool:
        return self.status is CalendarEventStatus.CANCELLED


@dataclass(frozen=True)
class CalendarEventPage:
    """One page of fetched events plus the pagination/sync cursors.

    ``next_page_token`` advances within a single list call; ``next_sync_token``
    appears only on the final page of a sync run and is stored for the next
    incremental pull.
    """

    events: tuple[CalendarEvent, ...]
    next_page_token: str | None = None
    next_sync_token: str | None = None
