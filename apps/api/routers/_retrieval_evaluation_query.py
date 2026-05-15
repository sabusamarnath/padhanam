"""Query-string parsers for the retrieval-evaluation HTTP routes (D112, S42).

Both list endpoints (``GET /gold-sets`` and ``GET /evaluation-runs``)
share the same cursor + page_size shape: an opaque base64 cursor
string for subsequent pages and a page_size query parameter (1..50)
for the first page. The use cases accept these as separate
parameters and own the codec invocation, so the parser just
validates the page_size range and forwards the cursor string
verbatim.

Page-size ceiling is ``PAGE_SIZE_CEILING`` from
``contexts/retrieval_evaluation/domain/query_filters.py`` (50,
matching the run_history precedent from S33 / D97).

Validation failures:

- Out-of-range ``page_size`` is caught by FastAPI's ``ge`` / ``le``
  on the Annotated type → 422.
- ``MalformedCursorError`` (raised on decode at the use-case
  boundary) translates to 400 via the registered handler at
  ``apps/api/_errors.py``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Query

from contexts.retrieval_evaluation.domain.query_filters import (
    PAGE_SIZE_CEILING,
)


def parse_gold_set_list_query(
    cursor: Annotated[str | None, Query()] = None,
    page_size: Annotated[
        int, Query(ge=1, le=PAGE_SIZE_CEILING)
    ] = 50,
) -> tuple[str | None, int]:
    """Return ``(encoded_cursor, page_size)`` for ``GET /gold-sets``."""
    return cursor, page_size


def parse_evaluation_run_list_query(
    cursor: Annotated[str | None, Query()] = None,
    page_size: Annotated[
        int, Query(ge=1, le=PAGE_SIZE_CEILING)
    ] = 20,
) -> tuple[str | None, int]:
    """Return ``(encoded_cursor, page_size)`` for ``GET /evaluation-runs``."""
    return cursor, page_size


__all__ = [
    "parse_evaluation_run_list_query",
    "parse_gold_set_list_query",
]
