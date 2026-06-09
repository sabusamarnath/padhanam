"""Meeting — the stored calendar artefact (D148).

A Meeting is the persisted, encrypted, indexable record minted from a
fetched CalendarEvent plus tenant context. It is a *mutable search cache*
keyed on the stable Google event id: deltas upsert modified events and
tombstone cancelled ones; a content change re-embeds and re-indexes. The
immutable evidence record is the audit-event payload snapshot taken at
citation time (the two-store split, D148) — not this row.

``to_search_text`` synthesises the structured fields into one text blob;
the same synthesis feeds embedding (commit 6) and the content hash used
to detect whether a delta actually changed content (and so must
re-embed). Framework-free per D16 — no vendor types here.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID

from contexts.calendar.domain.calendar_event import (
    CalendarEvent,
    CalendarEventStatus,
)


class MeetingStatus(StrEnum):
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class MeetingAttendee:
    email: str | None
    display_name: str | None
    response_status: str | None
    organizer: bool = False


@dataclass(frozen=True)
class Meeting:
    id: UUID
    tenant_id: UUID
    jurisdiction: str
    google_event_id: str
    status: MeetingStatus
    title: str | None
    description: str | None
    location: str | None
    attendees: tuple[MeetingAttendee, ...]
    organizer_email: str | None
    start_at: datetime | None
    end_at: datetime | None
    start_raw: str | None
    end_raw: str | None
    source_updated_at: datetime | None
    recurring_event_id: str | None
    html_link: str | None
    content_hash: str | None
    created_at: datetime
    updated_at: datetime
    cancelled_at: datetime | None = None
    # The connection-scoped calendar identity (D176). Value is the calendar
    # connection's id at the current primary-only pull (one connection = one
    # account's primary calendar); part of the Meeting identity key
    # (tenant_id, calendar_id, google_event_id) so two accounts whose primary
    # calendars share a Google event id do not collide. Defaults empty for
    # pure-domain test construction; the sync path always sets it.
    calendar_id: str = ""

    def __post_init__(self) -> None:
        if not self.jurisdiction or not self.jurisdiction.strip():
            raise ValueError("Meeting.jurisdiction must be non-empty")
        if not self.google_event_id or not self.google_event_id.strip():
            raise ValueError("Meeting.google_event_id must be non-empty")
        if self.updated_at < self.created_at:
            raise ValueError("Meeting.updated_at must be >= created_at")

    @property
    def is_cancelled(self) -> bool:
        return self.status is MeetingStatus.CANCELLED

    def to_search_text(self) -> str:
        return synthesise_meeting_text(
            title=self.title,
            description=self.description,
            location=self.location,
            attendees=self.attendees,
            organizer_email=self.organizer_email,
        )


def synthesise_meeting_text(
    *,
    title: str | None,
    description: str | None,
    location: str | None,
    attendees: tuple[MeetingAttendee, ...],
    organizer_email: str | None,
) -> str:
    """Flatten a Meeting's structured content into one searchable text blob.

    This is the Meeting→text step the substrate-inheritance survey names:
    it replaces ingestion's parser so the inherited embedder and graph
    ports see text. Deterministic field order so the content hash is
    stable across runs.
    """
    lines: list[str] = []
    if title:
        lines.append(f"Title: {title}")
    if description:
        lines.append(f"Description: {description}")
    if location:
        lines.append(f"Location: {location}")
    if organizer_email:
        lines.append(f"Organizer: {organizer_email}")
    attendee_labels = [
        a.display_name or a.email
        for a in attendees
        if (a.display_name or a.email)
    ]
    if attendee_labels:
        lines.append("Attendees: " + ", ".join(attendee_labels))
    return "\n".join(lines)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_dt(value: str | None) -> datetime | None:
    """Best-effort parse of a Google start/end value to an aware datetime.

    Timed events carry an RFC3339 ``dateTime`` (with offset); all-day
    events carry a ``date`` (no time). All-day dates are anchored at
    midnight UTC for indexing; the raw value is preserved separately.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def meeting_from_event(
    event: CalendarEvent,
    *,
    tenant_id: UUID,
    jurisdiction: str,
    meeting_id: UUID,
    now: datetime,
    created_at: datetime | None = None,
    calendar_id: str = "",
) -> Meeting:
    """Map a live (non-cancelled) fetched event to a stored Meeting.

    Cancelled tombstones do not flow through here — the pipeline calls the
    repository's tombstone path for those, which purges content. Computes
    the content hash from the synthesised text so the pipeline can detect a
    real content change and trigger re-embedding.
    """
    attendees = tuple(
        MeetingAttendee(
            email=a.email,
            display_name=a.display_name,
            response_status=a.response_status,
            organizer=a.organizer,
        )
        for a in event.attendees
    )
    status = (
        MeetingStatus(event.status.value)
        if event.status is not CalendarEventStatus.CANCELLED
        else MeetingStatus.CANCELLED
    )
    text = synthesise_meeting_text(
        title=event.summary,
        description=event.description,
        location=event.location,
        attendees=attendees,
        organizer_email=event.organizer_email,
    )
    return Meeting(
        id=meeting_id,
        tenant_id=tenant_id,
        jurisdiction=jurisdiction,
        calendar_id=calendar_id,
        google_event_id=event.google_event_id,
        status=status,
        title=event.summary,
        description=event.description,
        location=event.location,
        attendees=attendees,
        organizer_email=event.organizer_email,
        start_at=_parse_dt(event.start),
        end_at=_parse_dt(event.end),
        start_raw=event.start,
        end_raw=event.end,
        source_updated_at=_parse_dt(event.updated),
        recurring_event_id=event.recurring_event_id,
        html_link=event.html_link,
        content_hash=_content_hash(text),
        created_at=created_at or now,
        updated_at=now,
    )
