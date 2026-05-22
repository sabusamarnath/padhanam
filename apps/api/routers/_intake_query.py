"""Query-string parser for the intake list endpoint (D127, S44b).

Maps the query parameters on ``GET /api/v1/intakes`` to the domain
value objects ``list_intakes`` consumes:

- ``source`` (repeated) -> ``IntakeListFilters.intake_sources``
- ``cursor`` (opaque base64 string) -> decoded ``IntakeListCursor`` or None
- ``page_size`` (int 1..PAGE_SIZE_CEILING)

An unknown ``source`` raises ``InvalidIntakeFilterError`` (400
``invalid_intake_filter``); a malformed ``cursor`` raises the intake
``MalformedCursorError`` (400 ``malformed_intake_cursor``);
out-of-range ``page_size`` is caught by FastAPI's ``ge`` / ``le`` (422).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Query

from contexts.intake.application.cursor import decode_intake_cursor
from contexts.intake.domain import IntakeSource
from contexts.intake.domain.query_filters import (
    PAGE_SIZE_CEILING,
    IntakeListCursor,
    IntakeListFilters,
)


class InvalidIntakeFilterError(ValueError):
    """Raised when a ``GET /intakes`` filter value is unknown.

    Translates to 400 ``invalid_intake_filter`` via the registered
    handler at ``apps/api/_errors.py``.
    """


def parse_intake_list_query(
    source: Annotated[list[str] | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_CEILING)] = 20,
) -> tuple[IntakeListFilters, IntakeListCursor | None, int]:
    """Parse the query string into ``(filters, cursor, page_size)``."""
    filters = IntakeListFilters(
        intake_sources=_parse_sources(source),
    )
    decoded = decode_intake_cursor(cursor) if cursor is not None else None
    return filters, decoded, page_size


def _parse_sources(
    raw: list[str] | None,
) -> tuple[IntakeSource, ...] | None:
    if not raw:
        return None
    parsed: list[IntakeSource] = []
    for value in raw:
        try:
            parsed.append(IntakeSource(value))
        except ValueError as exc:
            valid = ", ".join(s.value for s in IntakeSource)
            raise InvalidIntakeFilterError(
                f"unknown source {value!r}; valid values: {valid}"
            ) from exc
    return tuple(parsed)


__all__ = ["InvalidIntakeFilterError", "parse_intake_list_query"]
