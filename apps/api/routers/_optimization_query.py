"""Query-string parsers for the optimization HTTP routes (D112, S42).

Two list endpoints:

- ``GET /optimization-runs`` — cursor + page_size only.
- ``GET /recommendations`` — cursor + page_size plus repeated
  ``category`` and ``status`` filter params that map to
  ``RecommendationListFilters``.

Page-size ceiling is ``PAGE_SIZE_CEILING`` from
``contexts/optimization/domain/query_filters.py`` (50, matching the
run_history precedent from S33 / D97).

Filter validation:

- Unknown category or status values raise ``InvalidOptimizationFilterError``
  which the registered handler translates to 400
  ``invalid_optimization_filter``.
- Out-of-range ``page_size`` is caught by FastAPI's ``ge`` / ``le``
  on the Annotated type → 422.
- ``MalformedCursorError`` (raised on decode at the use-case
  boundary) translates to 400 via the registered handler.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Query

from contexts.optimization.domain.category import RecommendationCategory
from contexts.optimization.domain.query_filters import (
    PAGE_SIZE_CEILING,
    RecommendationListFilters,
)
from contexts.optimization.domain.recommendation_status import (
    RecommendationStatus,
)


class InvalidOptimizationFilterError(ValueError):
    """Raised when a ``GET /recommendations`` filter value is unknown.

    Translates to 400 ``invalid_optimization_filter`` via the
    registered handler at ``apps/api/_errors.py``.
    """


def parse_optimization_run_list_query(
    cursor: Annotated[str | None, Query()] = None,
    page_size: Annotated[
        int, Query(ge=1, le=PAGE_SIZE_CEILING)
    ] = 20,
) -> tuple[str | None, int]:
    """Return ``(encoded_cursor, page_size)`` for ``GET /optimization-runs``."""
    return cursor, page_size


def parse_recommendation_list_query(
    cursor: Annotated[str | None, Query()] = None,
    page_size: Annotated[
        int, Query(ge=1, le=PAGE_SIZE_CEILING)
    ] = 20,
    category: Annotated[list[str] | None, Query()] = None,
    status: Annotated[list[str] | None, Query()] = None,
) -> tuple[RecommendationListFilters, str | None, int]:
    """Return ``(filters, encoded_cursor, page_size)`` for ``GET /recommendations``.

    ``category`` and ``status`` are repeated query parameters; empty
    lists collapse to ``None`` at the domain layer per the
    ``RecommendationListFilters`` ``__post_init__`` invariant.
    """
    categories = _parse_categories(category)
    statuses = _parse_statuses(status)
    filters = RecommendationListFilters(
        categories=categories,
        statuses=statuses,
    )
    return filters, cursor, page_size


def _parse_categories(
    raw: list[str] | None,
) -> tuple[RecommendationCategory, ...] | None:
    if not raw:
        return None
    parsed: list[RecommendationCategory] = []
    for value in raw:
        try:
            parsed.append(RecommendationCategory(value))
        except ValueError as exc:
            valid = ", ".join(c.value for c in RecommendationCategory)
            raise InvalidOptimizationFilterError(
                f"unknown category {value!r}; valid values: {valid}"
            ) from exc
    return tuple(parsed)


def _parse_statuses(
    raw: list[str] | None,
) -> tuple[RecommendationStatus, ...] | None:
    if not raw:
        return None
    parsed: list[RecommendationStatus] = []
    for value in raw:
        try:
            parsed.append(RecommendationStatus(value))
        except ValueError as exc:
            valid = ", ".join(s.value for s in RecommendationStatus)
            raise InvalidOptimizationFilterError(
                f"unknown status {value!r}; valid values: {valid}"
            ) from exc
    return tuple(parsed)


__all__ = [
    "InvalidOptimizationFilterError",
    "parse_optimization_run_list_query",
    "parse_recommendation_list_query",
]
