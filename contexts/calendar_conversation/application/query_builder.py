"""Query builder — filter the Meeting store by a typed calendar intent (D148, P15, S55b-1).

The MeetingReader exposes ``list_meetings`` (the tenant's stored, non-
cancelled meetings); the calendar-conversation cell filters that list in
memory by the resolved intent. Pure functions on ``Meeting`` value
objects — framework-free, no I/O. Date-window resolution is UTC-anchored
and deterministic so tests pin a fixed ``now``.

The Meeting store is a small per-personal-calendar cache (D149: 3 events
in the smoke; tens at most at Phase 2-A), so in-memory filtering is the
honest minimum; pgvector similarity search over the meetings table is a
substrate the reader does not yet expose at the conversation surface and
is a forward enhancement, not built here.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from contexts.calendar.domain.meeting import Meeting

# Reuse the audit cell's case-reference resolver shape for title matching.
import re

_TITLE_STOPWORDS: frozenset[str] = frozenset(
    {
        "the", "a", "an", "my", "our", "this", "that", "these", "those",
        "to", "of", "for", "in", "on", "and", "or", "with", "about",
        "meeting", "meetings", "event", "events", "call", "calls",
        "calendar", "appointment", "appointments",
    }
)


def _day_bounds(day: datetime) -> tuple[datetime, datetime]:
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def resolve_window(range_keyword: str, *, now: datetime) -> tuple[datetime, datetime]:
    """Resolve a relative range keyword to a concrete [start, end) UTC window.

    Raises ``ValueError`` for an unknown keyword so the cell can surface a
    clarification rather than silently returning the whole calendar.
    """
    now = now.astimezone(timezone.utc)
    today_start, today_end = _day_bounds(now)
    if range_keyword == "today":
        return today_start, today_end
    if range_keyword == "tomorrow":
        return today_end, today_end + timedelta(days=1)
    if range_keyword == "this_week":
        # ISO week: Monday 00:00 of this week to the next Monday.
        monday = today_start - timedelta(days=now.weekday())
        return monday, monday + timedelta(days=7)
    if range_keyword == "next_week":
        monday = today_start - timedelta(days=now.weekday())
        next_monday = monday + timedelta(days=7)
        return next_monday, next_monday + timedelta(days=7)
    if range_keyword == "this_month":
        first = today_start.replace(day=1)
        if first.month == 12:
            next_first = first.replace(year=first.year + 1, month=1)
        else:
            next_first = first.replace(month=first.month + 1)
        return first, next_first
    raise ValueError(f"unknown range_keyword {range_keyword!r}")


def _scheduled(meetings: tuple[Meeting, ...]) -> list[Meeting]:
    """Non-cancelled meetings carrying a parseable start, soonest first."""
    scheduled = [
        m for m in meetings if not m.is_cancelled and m.start_at is not None
    ]
    scheduled.sort(key=lambda m: m.start_at)  # type: ignore[arg-type,return-value]
    return scheduled


def meetings_in_window(
    meetings: tuple[Meeting, ...], *, start: datetime, end: datetime
) -> tuple[Meeting, ...]:
    """Meetings whose start falls in [start, end), soonest first."""
    return tuple(
        m
        for m in _scheduled(meetings)
        if start <= m.start_at.astimezone(timezone.utc) < end  # type: ignore[union-attr]
    )


def meetings_with_attendee(
    meetings: tuple[Meeting, ...], *, attendee: str
) -> tuple[Meeting, ...]:
    """Meetings whose attendee or organizer label contains the reference.

    Case-insensitive substring match against each attendee's display name
    and email plus the organizer email — the honest minimum for a personal
    calendar; fuzzy name resolution is a forward enhancement.
    """
    needle = attendee.strip().lower()
    if not needle:
        return ()
    matched: list[Meeting] = []
    for m in _scheduled(meetings):
        labels: list[str] = []
        for a in m.attendees:
            if a.display_name:
                labels.append(a.display_name.lower())
            if a.email:
                labels.append(a.email.lower())
        if m.organizer_email:
            labels.append(m.organizer_email.lower())
        if any(needle in label for label in labels):
            matched.append(m)
    return tuple(matched)


def next_meeting(
    meetings: tuple[Meeting, ...], *, now: datetime
) -> Meeting | None:
    """The soonest non-cancelled meeting starting at or after ``now``."""
    now = now.astimezone(timezone.utc)
    for m in _scheduled(meetings):
        if m.start_at.astimezone(timezone.utc) >= now:  # type: ignore[union-attr]
            return m
    return None


def title_tokens(text: str) -> frozenset[str]:
    """Lowercase, split on non-alphanumerics, drop calendar-context stopwords."""
    return frozenset(
        word
        for word in re.split(r"[^a-z0-9]+", text.lower())
        if word and word not in _TITLE_STOPWORDS
    )


def _fold_by_series(meetings: list[Meeting]) -> list[Meeting]:
    """One representative per recurring source series (D175 reaching the title
    resolution; the same fold the orphan/coverage reads use).

    A recurring event's many same-titled instances (a daily medication, ~120
    instances) collapse to one representative keyed on ``recurring_event_id``;
    a one-off is its own (keyed on its id). Without this, opening a recurring
    event matched all its instances and forced a "choose among 122 meetings"
    resolution clarification — overwhelming, and on the web path it 500'd
    (the clarification's PendingClarification has no real originating intake).
    """
    seen: dict[object, Meeting] = {}
    order: list[object] = []
    for m in meetings:
        key: object = m.recurring_event_id or ("solo", m.id)
        if key not in seen:
            seen[key] = m
            order.append(key)
    return [seen[k] for k in order]


def resolve_title_reference(
    reference: str, meetings: tuple[Meeting, ...]
) -> tuple[Meeting | None, tuple[Meeting, ...]]:
    """Resolve a natural-language title reference against stored meetings.

    Returns ``(matched, ())`` on exactly-one best match; ``(None, candidates)``
    on a multi-match top-scoring tie (D139 resolution-ambiguity); ``(None, ())``
    on no match. Recurring instances are folded by source series first (D175),
    so a recurring event resolves to one representative rather than N instances.
    Mirrors the audit cell's ``_resolve_case_reference``.
    """
    ref_tokens = title_tokens(reference)
    candidates = [
        m for m in meetings if not m.is_cancelled and m.title
    ]
    if not ref_tokens or not candidates:
        return None, ()

    exact = _fold_by_series(
        [m for m in candidates if title_tokens(m.title or "") == ref_tokens]
    )
    if len(exact) == 1:
        return exact[0], ()
    if len(exact) > 1:
        return None, tuple(exact)

    scored = [
        (len(ref_tokens & title_tokens(m.title or "")), m) for m in candidates
    ]
    best = max(score for score, _ in scored)
    if best == 0:
        return None, ()
    winners = _fold_by_series([m for score, m in scored if score == best])
    if len(winners) == 1:
        return winners[0], ()
    return None, tuple(winners)


__all__ = [
    "meetings_in_window",
    "meetings_with_attendee",
    "next_meeting",
    "resolve_title_reference",
    "resolve_window",
    "title_tokens",
]
