"""Query-string parser for the audit-event list endpoints (D103, S37).

Maps the eight filter query parameters on ``GET /audit/events`` and
``GET /platform/audit/events`` to the domain value objects the
``AuditEventReader`` port consumes plus ``cursor`` and ``page_size``:

- ``timestamp_range_start`` + ``timestamp_range_end`` (paired)
  -> ``AuditEventListFilters.timestamp_range``.
- ``actor`` (single, exact match) -> ``AuditEventListFilters.actor``.
- ``action_verb`` (repeated) -> ``AuditEventListFilters.action_verbs``.
- ``resource_type`` (single) -> ``AuditEventListFilters.resource_type``.
- ``resource_id`` (single, only valid with ``resource_type``)
  -> ``AuditEventListFilters.resource_id``.
- ``correlation_id`` (single, exact match)
  -> ``AuditEventListFilters.correlation_id``.
- ``jurisdiction`` (repeated, multi-value match per D102 domain shape)
  -> ``AuditEventListFilters.jurisdiction``.
- ``cursor`` (opaque base64 string) -> decoded ``AuditEventListCursor``
  or ``None``.
- ``page_size`` (int 1..PAGE_SIZE_CEILING).

Empty repeated params and ``None`` both collapse to ``None`` (no-filter)
per the S36 ``AuditEventListFilters`` ``__post_init__`` normalisation.

The parser raises:

- ``InvalidAuditFilterError`` when ``timestamp_range_start`` and
  ``timestamp_range_end`` are not both provided, when the lower bound
  is not strictly earlier than the upper bound, or when
  ``resource_id`` is supplied without ``resource_type``. The HTTP
  exception handler at S37 commit 4 translates to 400 with code
  ``invalid_audit_filter``.
- ``MalformedCursorError`` (re-raised from
  ``contexts.audit.application.cursor.decode``) when ``cursor``
  cannot be decoded. The HTTP exception handler translates to 400
  with code ``malformed_audit_cursor``.

The parser returns ``(filters, cursor, page_size)`` — three values
rather than the run-history two — because the audit port's
``list_audit_events_with_filters`` takes ``page_size`` as a separate
parameter alongside the optional cursor (the adapter overrides
``page_size`` with ``cursor.page_size`` when both are present; the
parser surfaces both so the route handler can pass them through
unchanged).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import Query

from contexts.audit.application.cursor import decode as decode_cursor
from contexts.audit.domain.query_filters import (
    PAGE_SIZE_CEILING,
    AuditEventListCursor,
    AuditEventListFilters,
    MalformedCursorError,
)


class InvalidAuditFilterError(ValueError):
    """Raised when audit query parameters are inconsistent (D103).

    Three cases at S37: (a) only one of
    ``timestamp_range_start``/``timestamp_range_end`` supplied;
    (b) timestamp lower bound not strictly earlier than upper;
    (c) ``resource_id`` supplied without ``resource_type``. The
    HTTP exception handler translates to 400 with code
    ``invalid_audit_filter``.
    """


def parse_audit_list_query(
    timestamp_range_start: Annotated[datetime | None, Query()] = None,
    timestamp_range_end: Annotated[datetime | None, Query()] = None,
    actor: Annotated[str | None, Query()] = None,
    action_verb: Annotated[list[str] | None, Query()] = None,
    resource_type: Annotated[str | None, Query()] = None,
    resource_id: Annotated[str | None, Query()] = None,
    correlation_id: Annotated[str | None, Query()] = None,
    jurisdiction: Annotated[list[str] | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    page_size: Annotated[
        int, Query(ge=1, le=PAGE_SIZE_CEILING)
    ] = PAGE_SIZE_CEILING,
) -> tuple[AuditEventListFilters, AuditEventListCursor | None, int]:
    """Parse query-string into ``(filters, cursor, page_size)``.

    FastAPI invokes this as a sub-dependency of the list routes via
    ``Depends(parse_audit_list_query)``. Validation failures raise
    ``InvalidAuditFilterError`` (translated to 400 at the error
    handler) or ``MalformedCursorError`` (same translation,
    different error code); out-of-range ``page_size`` is caught
    earlier by FastAPI's ``ge``/``le`` and surfaces as a 422
    validation error per the existing handler.
    """
    timestamp_range = _validate_timestamp_range(
        timestamp_range_start, timestamp_range_end
    )

    try:
        filters = AuditEventListFilters(
            timestamp_range=timestamp_range,
            actor=actor,
            action_verbs=tuple(action_verb) if action_verb else None,
            resource_type=resource_type,
            resource_id=resource_id,
            correlation_id=correlation_id,
            jurisdiction=tuple(jurisdiction) if jurisdiction else None,
        )
    except ValueError as exc:
        # AuditEventListFilters.__post_init__ raises ValueError on the
        # resource_id-without-resource_type case (and on non-empty
        # string violations). Re-raise as the typed audit-filter error
        # so the HTTP handler surfaces a typed 400 path rather than
        # a generic ValidationError leaking the dataclass field name.
        raise InvalidAuditFilterError(str(exc)) from exc

    resolved_cursor = decode_cursor(cursor) if cursor is not None else None

    return filters, resolved_cursor, page_size


def _validate_timestamp_range(
    timestamp_range_start: datetime | None,
    timestamp_range_end: datetime | None,
) -> tuple[datetime, datetime] | None:
    """Map paired timestamp params into the filter's range tuple."""
    if timestamp_range_start is None and timestamp_range_end is None:
        return None
    if timestamp_range_start is None or timestamp_range_end is None:
        raise InvalidAuditFilterError(
            "timestamp_range_start and timestamp_range_end must both be "
            "provided or both omitted; got "
            f"timestamp_range_start={timestamp_range_start!r} "
            f"timestamp_range_end={timestamp_range_end!r}"
        )
    if timestamp_range_start >= timestamp_range_end:
        raise InvalidAuditFilterError(
            "timestamp_range_start must be strictly earlier than "
            "timestamp_range_end; got "
            f"timestamp_range_start={timestamp_range_start.isoformat()} "
            f"timestamp_range_end={timestamp_range_end.isoformat()}"
        )
    return (timestamp_range_start, timestamp_range_end)


__all__ = [
    "InvalidAuditFilterError",
    "MalformedCursorError",
    "parse_audit_list_query",
]
