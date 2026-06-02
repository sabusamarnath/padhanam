"""Unit tests for calendar-conversation intent parsing (D148, S55b-1)."""

from __future__ import annotations

from contexts.calendar_conversation.domain.intent import (
    CalendarIntentType,
    FindByAttendee,
    FindByDateRange,
    FindByTitle,
    FindNextMeeting,
    UnclearCalendarIntent,
    calendar_intent_type_of,
    parse_calendar_intent,
)
from shared_kernel.intent_classification_calendar import (
    CALENDAR_INTENT_EXTRACTION_SCHEMA,
)


def test_parse_each_intent_class() -> None:
    assert parse_calendar_intent(
        {"intent_class": "find_by_date_range", "range_keyword": "today"}
    ) == FindByDateRange(range_keyword="today")
    assert parse_calendar_intent(
        {"intent_class": "find_by_attendee", "attendee": "Ada"}
    ) == FindByAttendee(attendee="Ada")
    assert parse_calendar_intent(
        {"intent_class": "find_by_title", "title_reference": "board sync"}
    ) == FindByTitle(title_reference="board sync")
    assert isinstance(
        parse_calendar_intent({"intent_class": "find_next_meeting"}),
        FindNextMeeting,
    )
    unclear = parse_calendar_intent(
        {"intent_class": "unclear_calendar", "clarification": "hm?"}
    )
    assert isinstance(unclear, UnclearCalendarIntent)
    assert unclear.clarification == "hm?"


def test_parse_coerces_unknown_and_missing_to_unclear() -> None:
    assert isinstance(parse_calendar_intent({}), UnclearCalendarIntent)
    assert isinstance(
        parse_calendar_intent({"intent_class": "nonsense"}),
        UnclearCalendarIntent,
    )
    # Missing required slot coerces to unclear, not a KeyError.
    assert isinstance(
        parse_calendar_intent({"intent_class": "find_by_attendee"}),
        UnclearCalendarIntent,
    )


def test_type_of_round_trips() -> None:
    for intent in (
        FindByDateRange(range_keyword="today"),
        FindByAttendee(attendee="Ada"),
        FindByTitle(title_reference="x"),
        FindNextMeeting(),
        UnclearCalendarIntent(clarification="?"),
    ):
        assert calendar_intent_type_of(intent) in {t.value for t in CalendarIntentType}


def test_schema_enum_matches_intent_type_values() -> None:
    # The schema enum and the StrEnum must not drift (single-source binding).
    schema_enum = set(
        CALENDAR_INTENT_EXTRACTION_SCHEMA["properties"]["intent_class"]["enum"]
    )
    assert schema_enum == {t.value for t in CalendarIntentType}
