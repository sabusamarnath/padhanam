"""Email-conversation intent prompt and schema — cross-cutting primitive (D137, D138, D151, P15, S56b).

Sibling to ``shared_kernel/intent_classification_calendar.py``. The
email-conversation cell consumes this module; the D137 evaluation runner
consumes the same primitive when running an email-conversation gold set
(the ``intent_surface`` field selects this surface). Single-source-of-truth
binding ensures the substrate measures what production runs.

Framework-free per D16 — schema is a plain dict; prompt builder is pure.
"""

from __future__ import annotations

from typing import Any


EMAIL_EXTRACTION_PREAMBLE: str = (
    "You extract a structured email-query intent from a message a busy "
    "professional sent their assistant. The message is a question about "
    "their email — messages in their inbox. Classify the message as "
    "find_by_date_range (emails in a relative time window), find_from_sender "
    "(emails from a named person), find_by_subject (a specific email or "
    "thread referenced by its subject), find_recent (the most recent emails, "
    "no other filter), or unclear_email (the message does not map cleanly to "
    "one of those, including requests to send/reply/delete which are not "
    "supported on this read-only surface). Fill only the fields relevant to "
    "the chosen intent; leave every other field as an empty string. For "
    "find_by_date_range, range_keyword is one of today, yesterday, "
    "this_week, last_week, this_month. Populate the confidence field with "
    "your self-reported confidence in the classification (0.0-1.0)."
)


EMAIL_INTENT_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent_class": {
            "type": "string",
            "enum": [
                "find_by_date_range",
                "find_from_sender",
                "find_by_subject",
                "find_recent",
                "unclear_email",
            ],
            "description": "the kind of email query the message asks for",
        },
        "range_keyword": {
            "type": "string",
            "description": (
                "the time-window keyword — one of today, yesterday, "
                "this_week, last_week, this_month — for find_by_date_range; "
                "empty string otherwise"
            ),
        },
        "sender": {
            "type": "string",
            "description": (
                "a person's name or email — for find_from_sender; empty "
                "string otherwise"
            ),
        },
        "subject_reference": {
            "type": "string",
            "description": (
                "a natural-language reference to a specific email's subject "
                "or thread — for find_by_subject; empty string otherwise"
            ),
        },
        "clarification": {
            "type": "string",
            "description": (
                "a short follow-up question the assistant should ask — for "
                "unclear_email; empty string otherwise"
            ),
        },
        "confidence": {
            "type": "number",
            "description": "self-reported confidence, 0.0-1.0",
            "minimum": 0.0,
            "maximum": 1.0,
        },
    },
    "required": [
        "intent_class",
        "range_keyword",
        "sender",
        "subject_reference",
        "clarification",
        "confidence",
    ],
    "additionalProperties": False,
}


def build_email_extraction_prompt(message: str) -> str:
    """Return the email-intent extraction prompt for a given user message."""
    return f"{EMAIL_EXTRACTION_PREAMBLE}\n\nMessage:\n{message}"


__all__ = [
    "EMAIL_EXTRACTION_PREAMBLE",
    "EMAIL_INTENT_EXTRACTION_SCHEMA",
    "build_email_extraction_prompt",
]
