"""Audit-conversation intent value objects (D137, D138, P14, S51).

The audit-conversation intent surface is distinct from the manual entry
cell's: the operator queries the audit chain rather than mutating
portfolio state. Six intent classes:

- ``FindByCase`` — events for a named Case (resolved by title).
- ``FindByDateRange`` — events in a time window.
- ``FindByActor`` — events authored by a named actor.
- ``FindByEventType`` — events of a given action verb.
- ``FindByCombination`` — events matching multiple optional filters.
- ``UnclearAuditIntent`` — the fallback for unrecognized queries.

Each typed intent is a frozen dataclass. The discriminated union plus
``parse_audit_intent`` mirrors the manual entry cell's
``parse_intent`` pattern at ``contexts/messaging/domain/intent.py``.
``IntentType`` values match the ``INTENT_CLASSES`` tuple addition at
``contexts/intent_classification_evaluation/domain/gold_set.py`` so
the gold-set fixture can reference them by string.

Framework-free per D16 — the domain layer is stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class AuditIntentType(StrEnum):
    """The intent class values for audit-conversation gold-set authoring."""

    FIND_BY_CASE = "find_by_case"
    FIND_BY_DATE_RANGE = "find_by_date_range"
    FIND_BY_ACTOR = "find_by_actor"
    FIND_BY_EVENT_TYPE = "find_by_event_type"
    FIND_BY_COMBINATION = "find_by_combination"
    UNCLEAR_AUDIT = "unclear_audit"


@dataclass(frozen=True)
class FindByCase:
    """Audit events for the case the operator named (resolved by title)."""

    case_reference: str


@dataclass(frozen=True)
class FindByDateRange:
    """Audit events in a relative time window.

    ``range_keyword`` carries an operator-facing relative descriptor —
    ``"today"``, ``"yesterday"``, ``"this_week"``, ``"last_week"``,
    ``"this_month"``, ``"last_month"`` — which the cell resolves to a
    concrete ``(start, end)`` window at composition time. Absolute date
    ranges defer to a future intent extension; the operator-dogfooding
    surface uses relative phrasings.
    """

    range_keyword: str


@dataclass(frozen=True)
class FindByActor:
    """Audit events authored by the named actor."""

    actor: str


@dataclass(frozen=True)
class FindByEventType:
    """Audit events of the named action verb (e.g. ``portfolio.case.create``)."""

    event_type: str


@dataclass(frozen=True)
class FindByCombination:
    """Audit events matching multiple optional filters in one query.

    All fields are optional; the cell composes filters that are set.
    """

    case_reference: str | None = None
    range_keyword: str | None = None
    actor: str | None = None
    event_type: str | None = None


@dataclass(frozen=True)
class UnclearAuditIntent:
    """The fallback intent when classification did not resolve to a known shape."""

    clarification: str


AuditIntent = (
    FindByCase
    | FindByDateRange
    | FindByActor
    | FindByEventType
    | FindByCombination
    | UnclearAuditIntent
)


def parse_audit_intent(raw: dict[str, Any]) -> AuditIntent:
    """Map a structured-output dict to a typed AuditIntent.

    Coerces to ``UnclearAuditIntent`` on any failure (missing intent_class,
    unknown class name, type errors). The cell catches parse failure
    upstream via ``StructuredOutputParseFailure``; this function only
    runs when ``StructuredOutputResponse.value`` is a dict.
    """
    intent_class = raw.get("intent_class")
    if not isinstance(intent_class, str):
        return UnclearAuditIntent(
            clarification="I could not interpret that as an audit query."
        )

    try:
        if intent_class == AuditIntentType.FIND_BY_CASE.value:
            return FindByCase(case_reference=str(raw["case_reference"]))
        if intent_class == AuditIntentType.FIND_BY_DATE_RANGE.value:
            return FindByDateRange(range_keyword=str(raw["range_keyword"]))
        if intent_class == AuditIntentType.FIND_BY_ACTOR.value:
            return FindByActor(actor=str(raw["actor"]))
        if intent_class == AuditIntentType.FIND_BY_EVENT_TYPE.value:
            return FindByEventType(event_type=str(raw["event_type"]))
        if intent_class == AuditIntentType.FIND_BY_COMBINATION.value:
            return FindByCombination(
                case_reference=_optional_str(raw.get("case_reference")),
                range_keyword=_optional_str(raw.get("range_keyword")),
                actor=_optional_str(raw.get("actor")),
                event_type=_optional_str(raw.get("event_type")),
            )
        if intent_class == AuditIntentType.UNCLEAR_AUDIT.value:
            return UnclearAuditIntent(
                clarification=str(
                    raw.get(
                        "clarification",
                        "I could not interpret that as an audit query.",
                    )
                )
            )
    except (KeyError, TypeError, ValueError):
        return UnclearAuditIntent(
            clarification="I could not interpret that as an audit query."
        )

    return UnclearAuditIntent(
        clarification="I could not interpret that as an audit query."
    )


def _optional_str(value: object) -> str | None:
    """Return a non-empty string from raw input, else None."""
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    if not value:
        return None
    return value


def audit_intent_type_of(intent: AuditIntent) -> str:
    """Return the AuditIntentType string value for a typed audit intent."""
    if isinstance(intent, FindByCase):
        return AuditIntentType.FIND_BY_CASE.value
    if isinstance(intent, FindByDateRange):
        return AuditIntentType.FIND_BY_DATE_RANGE.value
    if isinstance(intent, FindByActor):
        return AuditIntentType.FIND_BY_ACTOR.value
    if isinstance(intent, FindByEventType):
        return AuditIntentType.FIND_BY_EVENT_TYPE.value
    if isinstance(intent, FindByCombination):
        return AuditIntentType.FIND_BY_COMBINATION.value
    return AuditIntentType.UNCLEAR_AUDIT.value


__all__ = [
    "AuditIntent",
    "AuditIntentType",
    "FindByActor",
    "FindByCase",
    "FindByCombination",
    "FindByDateRange",
    "FindByEventType",
    "UnclearAuditIntent",
    "audit_intent_type_of",
    "parse_audit_intent",
]
