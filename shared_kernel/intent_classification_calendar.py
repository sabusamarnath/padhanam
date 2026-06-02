"""Calendar-conversation intent prompt and schema — cross-cutting primitive (D137, D138, D148, P15, S55b-1).

Sibling to ``shared_kernel/intent_classification_audit.py`` (the audit-
conversation cell's prompt+schema primitive). The calendar-conversation
cell consumes this module; the D137 evaluation runner at
``contexts/intent_classification_evaluation/`` consumes the same
primitive when running a calendar-conversation gold set (the
``intent_surface`` field selects this surface). Single-source-of-truth
structural binding ensures the substrate measures what production runs.

Framework-free per D16 — schema is a plain dict; prompt builder is a
pure function on strings.
"""

from __future__ import annotations

from typing import Any


CALENDAR_EXTRACTION_PREAMBLE: str = (
    "You extract a structured calendar-query intent from a message a busy "
    "professional sent their assistant. The message is a question about "
    "the operator's calendar — meetings, events, schedule. Classify the "
    "message as find_by_date_range (meetings in a relative time window), "
    "find_by_attendee (meetings with a named person), find_by_title (a "
    "specific meeting referenced by its title or subject), find_next_meeting "
    "(the operator's next upcoming meeting), or unclear_calendar (the "
    "message does not map cleanly to one of those). Fill only the fields "
    "relevant to the chosen intent; leave every other field as an empty "
    "string. For find_by_date_range, range_keyword is one of today, "
    "tomorrow, this_week, next_week, this_month. Populate the confidence "
    "field with your self-reported confidence in the classification "
    "(0.0-1.0)."
)


# JSON Schema (strict-mode) the calendar-intent extraction call conforms
# to. Flat object; every field is required; non-applicable fields come
# back as empty strings. The intent_class enum values match the
# ``contexts.calendar_conversation.domain.intent.CalendarIntentType``
# StrEnum values; a unit test asserts the alignment so the duplication
# does not drift silently.
CALENDAR_INTENT_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent_class": {
            "type": "string",
            "enum": [
                "find_by_date_range",
                "find_by_attendee",
                "find_by_title",
                "find_next_meeting",
                "unclear_calendar",
            ],
            "description": "the kind of calendar query the message asks for",
        },
        "range_keyword": {
            "type": "string",
            "description": (
                "the time-window keyword — one of today, tomorrow, "
                "this_week, next_week, this_month — for find_by_date_range; "
                "empty string otherwise"
            ),
        },
        "attendee": {
            "type": "string",
            "description": (
                "a person's name or email — for find_by_attendee; empty "
                "string otherwise"
            ),
        },
        "title_reference": {
            "type": "string",
            "description": (
                "a natural-language reference to a specific meeting's title "
                "or subject — for find_by_title; empty string otherwise"
            ),
        },
        "clarification": {
            "type": "string",
            "description": (
                "a short follow-up question the assistant should ask — for "
                "unclear_calendar; empty string otherwise"
            ),
        },
        "confidence": {
            "type": "number",
            "description": (
                "self-reported confidence in the classification, 0.0-1.0"
            ),
            "minimum": 0.0,
            "maximum": 1.0,
        },
    },
    "required": [
        "intent_class",
        "range_keyword",
        "attendee",
        "title_reference",
        "clarification",
        "confidence",
    ],
    "additionalProperties": False,
}


def build_calendar_extraction_prompt(message: str) -> str:
    """Return the calendar-intent extraction prompt for a given user message."""
    return f"{CALENDAR_EXTRACTION_PREAMBLE}\n\nMessage:\n{message}"


__all__ = [
    "CALENDAR_EXTRACTION_PREAMBLE",
    "CALENDAR_INTENT_EXTRACTION_SCHEMA",
    "build_calendar_extraction_prompt",
]
