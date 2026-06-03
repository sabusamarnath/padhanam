"""Email-conversation intent value objects (D137, D138, D151, P15, S56b).

Mirrors the calendar-conversation intent surface. Five intent classes:

- ``FindByDateRange`` — emails in a relative time window.
- ``FindFromSender`` — emails from a named person.
- ``FindBySubject`` — a specific email/thread by subject (the
  resolution-ambiguity carrier per D139).
- ``FindRecent`` — the most recent emails (no other filter).
- ``UnclearEmailIntent`` — the fallback (incl. send/reply/delete, which the
  read-only surface does not support).

``EmailIntentType`` values match ``EMAIL_INTENT_EXTRACTION_SCHEMA`` and the
gold-set ``INTENT_CLASSES``; a unit test asserts the alignment.
Framework-free per D16.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class EmailIntentType(StrEnum):
    FIND_BY_DATE_RANGE = "find_by_date_range"
    FIND_FROM_SENDER = "find_from_sender"
    FIND_BY_SUBJECT = "find_by_subject"
    FIND_RECENT = "find_recent"
    UNCLEAR_EMAIL = "unclear_email"


RANGE_KEYWORDS: frozenset[str] = frozenset(
    {"today", "yesterday", "this_week", "last_week", "this_month"}
)


@dataclass(frozen=True)
class FindByDateRange:
    range_keyword: str


@dataclass(frozen=True)
class FindFromSender:
    sender: str


@dataclass(frozen=True)
class FindBySubject:
    subject_reference: str


@dataclass(frozen=True)
class FindRecent:
    pass


@dataclass(frozen=True)
class UnclearEmailIntent:
    clarification: str


EmailIntent = (
    FindByDateRange | FindFromSender | FindBySubject | FindRecent | UnclearEmailIntent
)

_FALLBACK = "I could not interpret that as an email query."


def parse_email_intent(raw: dict[str, Any]) -> EmailIntent:
    """Map a structured-output dict to a typed EmailIntent (coerce to unclear on failure)."""
    intent_class = raw.get("intent_class")
    if not isinstance(intent_class, str):
        return UnclearEmailIntent(clarification=_FALLBACK)
    try:
        if intent_class == EmailIntentType.FIND_BY_DATE_RANGE.value:
            return FindByDateRange(range_keyword=str(raw["range_keyword"]))
        if intent_class == EmailIntentType.FIND_FROM_SENDER.value:
            return FindFromSender(sender=str(raw["sender"]))
        if intent_class == EmailIntentType.FIND_BY_SUBJECT.value:
            return FindBySubject(subject_reference=str(raw["subject_reference"]))
        if intent_class == EmailIntentType.FIND_RECENT.value:
            return FindRecent()
        if intent_class == EmailIntentType.UNCLEAR_EMAIL.value:
            return UnclearEmailIntent(
                clarification=str(raw.get("clarification", _FALLBACK))
            )
    except (KeyError, TypeError, ValueError):
        return UnclearEmailIntent(clarification=_FALLBACK)
    return UnclearEmailIntent(clarification=_FALLBACK)


def email_intent_type_of(intent: EmailIntent) -> str:
    if isinstance(intent, FindByDateRange):
        return EmailIntentType.FIND_BY_DATE_RANGE.value
    if isinstance(intent, FindFromSender):
        return EmailIntentType.FIND_FROM_SENDER.value
    if isinstance(intent, FindBySubject):
        return EmailIntentType.FIND_BY_SUBJECT.value
    if isinstance(intent, FindRecent):
        return EmailIntentType.FIND_RECENT.value
    return EmailIntentType.UNCLEAR_EMAIL.value


__all__ = [
    "EmailIntent",
    "EmailIntentType",
    "FindByDateRange",
    "FindBySubject",
    "FindFromSender",
    "FindRecent",
    "RANGE_KEYWORDS",
    "UnclearEmailIntent",
    "email_intent_type_of",
    "parse_email_intent",
]
