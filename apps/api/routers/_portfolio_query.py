"""Query-string parser for the portfolio list endpoint (D124, S43b).

Maps the four query parameters on ``GET /api/v1/portfolio/cases`` to
the domain value objects the reader consumes:

- ``case_type`` (repeated) -> ``CaseListFilters.case_types``
- ``status`` (repeated) -> ``CaseListFilters.statuses``
- ``cursor`` (opaque base64 string) -> decoded ``CaseListCursor`` or None
- ``page_size`` (int 1..PAGE_SIZE_CEILING)

Unknown ``case_type`` / ``status`` values raise
``InvalidPortfolioFilterError`` (400 ``invalid_portfolio_filter``);
a malformed ``cursor`` raises the portfolio ``MalformedCursorError``
(400 ``malformed_portfolio_cursor``); out-of-range ``page_size`` is
caught by FastAPI's ``ge`` / ``le`` (422).

The cursor is decoded here — the run-history pattern — because the
``list_cases`` use case consumes a decoded ``CaseListCursor``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Query

from contexts.portfolio.application.cursor import decode_case_cursor
from contexts.portfolio.domain import CaseStatus, CaseType
from contexts.portfolio.domain.query_filters import (
    PAGE_SIZE_CEILING,
    CaseListCursor,
    CaseListFilters,
)


class InvalidPortfolioFilterError(ValueError):
    """Raised when a ``GET /cases`` filter value is unknown.

    Translates to 400 ``invalid_portfolio_filter`` via the registered
    handler at ``apps/api/_errors.py``.
    """


def parse_case_list_query(
    case_type: Annotated[list[str] | None, Query()] = None,
    status: Annotated[list[str] | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_CEILING)] = 20,
) -> tuple[CaseListFilters, CaseListCursor | None, int]:
    """Parse the query string into ``(filters, cursor, page_size)``.

    FastAPI invokes this as a sub-dependency of ``GET /cases`` via
    ``Depends(parse_case_list_query)``.
    """
    filters = CaseListFilters(
        case_types=_parse_case_types(case_type),
        statuses=_parse_statuses(status),
    )
    decoded = decode_case_cursor(cursor) if cursor is not None else None
    return filters, decoded, page_size


def _parse_case_types(
    raw: list[str] | None,
) -> tuple[CaseType, ...] | None:
    if not raw:
        return None
    parsed: list[CaseType] = []
    for value in raw:
        try:
            parsed.append(CaseType(value))
        except ValueError as exc:
            valid = ", ".join(c.value for c in CaseType)
            raise InvalidPortfolioFilterError(
                f"unknown case_type {value!r}; valid values: {valid}"
            ) from exc
    return tuple(parsed)


def _parse_statuses(
    raw: list[str] | None,
) -> tuple[CaseStatus, ...] | None:
    if not raw:
        return None
    parsed: list[CaseStatus] = []
    for value in raw:
        try:
            parsed.append(CaseStatus(value))
        except ValueError as exc:
            valid = ", ".join(s.value for s in CaseStatus)
            raise InvalidPortfolioFilterError(
                f"unknown status {value!r}; valid values: {valid}"
            ) from exc
    return tuple(parsed)


__all__ = ["InvalidPortfolioFilterError", "parse_case_list_query"]
