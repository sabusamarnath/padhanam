"""Translate classified audit intents to AuditEventListFilters (P14, S51).

The cell consumes the existing ``AuditEventReader`` port from S36, which
takes ``AuditEventListFilters`` from
``contexts.audit.domain.query_filters``. The query builder maps each
typed audit intent value object to the corresponding filter shape:

- ``FindByCase`` -> ``resource_type='case'`` + ``resource_id=<case_uuid>``.
- ``FindByDateRange`` -> ``timestamp_range=(start, end)`` computed from
  the relative range keyword against the current time.
- ``FindByActor`` -> ``actor=<actor_value>``.
- ``FindByEventType`` -> ``action_verbs=(<verb>,)``.
- ``FindByCombination`` -> any combination of the above.

The relative-range-keyword resolution accepts the six keyword values
the audit prompt commits (``today``, ``yesterday``, ``this_week``,
``last_week``, ``this_month``, ``last_month``). Unknown keywords raise
``ValueError`` at builder construction.

Framework-free; stdlib only.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from contexts.audit.domain.query_filters import AuditEventListFilters

from contexts.audit_conversation.domain.intent import (
    FindByActor,
    FindByCase,
    FindByCombination,
    FindByDateRange,
    FindByEventType,
)


_KNOWN_RANGE_KEYWORDS: frozenset[str] = frozenset(
    {
        "today",
        "yesterday",
        "this_week",
        "last_week",
        "this_month",
        "last_month",
    }
)


def build_filters_for_case(
    intent: FindByCase, *, resolved_case_id: UUID
) -> AuditEventListFilters:
    """Filters for a case-scoped audit query.

    Caller resolves the intent's case_reference to a concrete case_id
    before invoking; resolution-ambiguity is handled at the cell layer.
    """
    return AuditEventListFilters(
        resource_type="case",
        resource_id=str(resolved_case_id),
    )


def build_filters_for_date_range(
    intent: FindByDateRange, *, now: datetime
) -> AuditEventListFilters:
    """Filters for a date-range audit query."""
    start, end = resolve_range_keyword(intent.range_keyword, now=now)
    return AuditEventListFilters(timestamp_range=(start, end))


def build_filters_for_actor(intent: FindByActor) -> AuditEventListFilters:
    """Filters for an actor-scoped audit query."""
    return AuditEventListFilters(actor=intent.actor)


def build_filters_for_event_type(
    intent: FindByEventType,
) -> AuditEventListFilters:
    """Filters for an event-type audit query."""
    return AuditEventListFilters(action_verbs=(intent.event_type,))


def build_filters_for_combination(
    intent: FindByCombination,
    *,
    resolved_case_id: UUID | None,
    now: datetime,
) -> AuditEventListFilters:
    """Filters for a combination audit query.

    Caller resolves ``case_reference`` to ``resolved_case_id`` ahead of
    time (or passes ``None`` when the intent did not name a case).
    """
    timestamp_range: tuple[datetime, datetime] | None = None
    if intent.range_keyword is not None:
        timestamp_range = resolve_range_keyword(intent.range_keyword, now=now)

    resource_type: str | None = None
    resource_id: str | None = None
    if resolved_case_id is not None:
        resource_type = "case"
        resource_id = str(resolved_case_id)

    action_verbs: tuple[str, ...] | None = None
    if intent.event_type is not None:
        action_verbs = (intent.event_type,)

    return AuditEventListFilters(
        timestamp_range=timestamp_range,
        actor=intent.actor,
        action_verbs=action_verbs,
        resource_type=resource_type,
        resource_id=resource_id,
    )


def resolve_range_keyword(
    keyword: str, *, now: datetime
) -> tuple[datetime, datetime]:
    """Map a relative range keyword to a concrete (start, end) window.

    Raises ``ValueError`` for unknown keywords.
    """
    if keyword not in _KNOWN_RANGE_KEYWORDS:
        raise ValueError(
            f"Unknown range_keyword {keyword!r}; expected one of "
            f"{sorted(_KNOWN_RANGE_KEYWORDS)}"
        )

    now_utc = now.astimezone(timezone.utc)

    if keyword == "today":
        start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now_utc

    if keyword == "yesterday":
        today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        start = today_start - timedelta(days=1)
        return start, today_start

    if keyword == "this_week":
        weekday = now_utc.weekday()
        week_start = now_utc.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=weekday)
        return week_start, now_utc

    if keyword == "last_week":
        weekday = now_utc.weekday()
        this_week_start = now_utc.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=weekday)
        last_week_start = this_week_start - timedelta(days=7)
        return last_week_start, this_week_start

    if keyword == "this_month":
        month_start = now_utc.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        return month_start, now_utc

    # keyword == "last_month"
    this_month_start = now_utc.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    # subtract one day to land in the previous month, then take its first day
    last_month_anywhere = this_month_start - timedelta(days=1)
    last_month_start = last_month_anywhere.replace(day=1)
    return last_month_start, this_month_start


__all__ = [
    "build_filters_for_actor",
    "build_filters_for_case",
    "build_filters_for_combination",
    "build_filters_for_date_range",
    "build_filters_for_event_type",
    "resolve_range_keyword",
]
