"""Calendar-conversation intent value objects (D137, D138, D148, P15, S55b-1).

The calendar-conversation intent surface lets the operator query their
calendar (the Meeting search cache) rather than mutate portfolio state.
Five intent classes:

- ``FindByDateRange`` — meetings in a relative time window.
- ``FindByAttendee`` — meetings with a named person.
- ``FindByTitle`` — a specific meeting referenced by title (resolved by
  title, the resolution-ambiguity carrier per D139).
- ``FindNextMeeting`` — the operator's next upcoming meeting.
- ``UnclearCalendarIntent`` — the fallback for unrecognized queries.

Each typed intent is a frozen dataclass. The discriminated union plus
``parse_calendar_intent`` mirrors the audit-conversation cell's
``parse_audit_intent`` pattern. ``CalendarIntentType`` values match the
``CALENDAR_INTENT_EXTRACTION_SCHEMA`` enum at
``shared_kernel/intent_classification_calendar.py`` and the gold-set
``INTENT_CLASSES`` addition; a unit test asserts the alignment so the
duplication does not drift silently.

Framework-free per D16 — the domain layer is stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class CalendarIntentType(StrEnum):
    """The intent class values for calendar-conversation gold-set authoring."""

    FIND_BY_DATE_RANGE = "find_by_date_range"
    FIND_BY_ATTENDEE = "find_by_attendee"
    FIND_BY_TITLE = "find_by_title"
    FIND_NEXT_MEETING = "find_next_meeting"
    UNCLEAR_CALENDAR = "unclear_calendar"


# Relative window keywords the cell resolves to a concrete (start, end).
RANGE_KEYWORDS: frozenset[str] = frozenset(
    {"today", "tomorrow", "this_week", "next_week", "this_month"}
)


@dataclass(frozen=True)
class FindByDateRange:
    """Meetings in a relative time window (``range_keyword``)."""

    range_keyword: str


@dataclass(frozen=True)
class FindByAttendee:
    """Meetings with the named person (matched against attendee labels)."""

    attendee: str


@dataclass(frozen=True)
class FindByTitle:
    """A specific meeting the operator named (resolved by title)."""

    title_reference: str


@dataclass(frozen=True)
class FindNextMeeting:
    """The operator's next upcoming (non-cancelled) meeting."""


@dataclass(frozen=True)
class UnclearCalendarIntent:
    """The fallback intent when classification did not resolve to a known shape."""

    clarification: str


CalendarIntent = (
    FindByDateRange
    | FindByAttendee
    | FindByTitle
    | FindNextMeeting
    | UnclearCalendarIntent
)


def parse_calendar_intent(raw: dict[str, Any]) -> CalendarIntent:
    """Map a structured-output dict to a typed CalendarIntent.

    Coerces to ``UnclearCalendarIntent`` on any failure (missing
    intent_class, unknown class name, type errors). The cell catches
    parse failure upstream via ``StructuredOutputParseFailure``; this
    function only runs when ``StructuredOutputResponse.value`` is a dict.
    """
    intent_class = raw.get("intent_class")
    if not isinstance(intent_class, str):
        return UnclearCalendarIntent(
            clarification="I could not interpret that as a calendar query."
        )

    try:
        if intent_class == CalendarIntentType.FIND_BY_DATE_RANGE.value:
            return FindByDateRange(range_keyword=str(raw["range_keyword"]))
        if intent_class == CalendarIntentType.FIND_BY_ATTENDEE.value:
            return FindByAttendee(attendee=str(raw["attendee"]))
        if intent_class == CalendarIntentType.FIND_BY_TITLE.value:
            return FindByTitle(title_reference=str(raw["title_reference"]))
        if intent_class == CalendarIntentType.FIND_NEXT_MEETING.value:
            return FindNextMeeting()
        if intent_class == CalendarIntentType.UNCLEAR_CALENDAR.value:
            return UnclearCalendarIntent(
                clarification=str(
                    raw.get(
                        "clarification",
                        "I could not interpret that as a calendar query.",
                    )
                )
            )
    except (KeyError, TypeError, ValueError):
        return UnclearCalendarIntent(
            clarification="I could not interpret that as a calendar query."
        )

    return UnclearCalendarIntent(
        clarification="I could not interpret that as a calendar query."
    )


def calendar_intent_type_of(intent: CalendarIntent) -> str:
    """Return the CalendarIntentType string value for a typed calendar intent."""
    if isinstance(intent, FindByDateRange):
        return CalendarIntentType.FIND_BY_DATE_RANGE.value
    if isinstance(intent, FindByAttendee):
        return CalendarIntentType.FIND_BY_ATTENDEE.value
    if isinstance(intent, FindByTitle):
        return CalendarIntentType.FIND_BY_TITLE.value
    if isinstance(intent, FindNextMeeting):
        return CalendarIntentType.FIND_NEXT_MEETING.value
    return CalendarIntentType.UNCLEAR_CALENDAR.value


__all__ = [
    "CalendarIntent",
    "CalendarIntentType",
    "FindByAttendee",
    "FindByDateRange",
    "FindByTitle",
    "FindNextMeeting",
    "RANGE_KEYWORDS",
    "UnclearCalendarIntent",
    "calendar_intent_type_of",
    "parse_calendar_intent",
]
