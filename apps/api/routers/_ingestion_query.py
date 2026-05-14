"""Query-string parser for the source-list endpoint (D104, S38).

Maps the two query parameters on ``GET /ingestion/sources`` to the
domain value objects the ``SourceRepositoryPort.list_sources`` use
case consumes:

- ``cursor`` (opaque base64 string) -> decoded ``SourceListCursor``
  or ``None``.
- ``page_size`` (int 1..PAGE_SIZE_CEILING).

S38 ships the minimum vocabulary per D104: no filter fields. Future
sessions extend the parser when a real consumer use case names a
filter dimension (state, file_type, jurisdiction); the surface is
intentionally narrow at Phase 1 close.

The parser raises:

- ``MalformedCursorError`` (re-raised from
  ``contexts.ingestion.application.cursor.decode``) when ``cursor``
  cannot be decoded. The HTTP exception handler at S38 translates
  to 400 with code ``malformed_ingestion_cursor``.

Out-of-range ``page_size`` is caught by FastAPI's ``ge``/``le``
validators and surfaces as a 422 validation error per the
existing ``register_run_history_error_handlers`` path; the
``RequestValidationError`` handler returns the
``ErrorResponse`` shape with error code ``validation_error``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Query

from contexts.ingestion.application.cursor import decode as decode_cursor
from contexts.ingestion.domain.source_list import (
    PAGE_SIZE_CEILING,
    MalformedCursorError,
    SourceListCursor,
)


def parse_source_list_query(
    cursor: Annotated[str | None, Query()] = None,
    page_size: Annotated[
        int, Query(ge=1, le=PAGE_SIZE_CEILING)
    ] = PAGE_SIZE_CEILING,
) -> tuple[SourceListCursor | None, int]:
    """Parse query-string into ``(cursor, page_size)``.

    FastAPI invokes this as a sub-dependency of the list route via
    ``Depends(parse_source_list_query)``. Validation failures raise
    ``MalformedCursorError`` (translated to 400 at the error
    handler); out-of-range ``page_size`` is caught earlier by
    FastAPI's ``ge``/``le`` and surfaces as a 422 validation error
    per the existing handler.
    """
    resolved_cursor = decode_cursor(cursor) if cursor is not None else None
    return resolved_cursor, page_size


__all__ = [
    "MalformedCursorError",
    "parse_source_list_query",
]
