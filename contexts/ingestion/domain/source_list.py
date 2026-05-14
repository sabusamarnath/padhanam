"""Cursor + page value objects for the source-list read surface (D104, S38).

``SourceListCursor`` encodes ``(created_at, id, page_size)`` for
tuple-comparison pagination on the ``(created_at DESC, id DESC)``
sort order, mirroring the audit reader's cursor pattern from S36
(D102). The page_size caps at ``PAGE_SIZE_CEILING`` (50, matching
the audit and run-history precedents) so the adapter cannot send
a malformed LIMIT.

``SourceListPage`` is the read port's return type for
``list_sources``: the sources tuple plus the optional next cursor.
Unlike the audit page, there is no chain-integrity field — the
ingestion substrate has no hash-chained integrity primitive at
P10 close.

``MalformedCursorError`` raises at decode time on base64, JSON,
schema, or type errors so the HTTP layer at S38 translates to
400 cleanly. Same shape as the audit and run-history precedents.

PAGE_SIZE_CEILING is the same 50 as audit / run-history. The
ingestion-management API at S38 is operator-facing read traffic
with no UI consumer materialised; the ceiling holds against
abuse without UX feedback.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from contexts.ingestion.domain.source import Source


PAGE_SIZE_CEILING: int = 50


class MalformedCursorError(Exception):
    """Raised when ``decode`` cannot reconstruct a ``SourceListCursor``.

    Covers base64 errors, malformed JSON, missing required fields,
    wrong field types, and out-of-range ``page_size``. The HTTP
    layer at S38 translates to 400; the port surface raises rather
    than returning a sentinel so the HTTP layer's exception handler
    is the single translation point. Mirror of the audit and
    run-history precedents.
    """


@dataclass(frozen=True)
class SourceListCursor:
    """Pagination cursor on ``(created_at, id, page_size)`` (D104).

    Tuple comparison against ``(created_at, id)`` paginates stably
    against the ``created_at DESC, id DESC`` sort order. ``page_size``
    must be in ``[1, PAGE_SIZE_CEILING]``; out-of-range values raise
    at construction time so the adapter cannot send a malformed
    LIMIT.

    Opaque to consumers at the HTTP boundary; the base64 + JSON
    encoding via ``contexts.ingestion.application.cursor`` is the
    serialisation shape.
    """

    created_at: datetime
    id: UUID
    page_size: int

    def __post_init__(self) -> None:
        if not (1 <= self.page_size <= PAGE_SIZE_CEILING):
            raise ValueError(
                f"page_size must be in [1, {PAGE_SIZE_CEILING}]; "
                f"got {self.page_size}"
            )


@dataclass(frozen=True)
class SourceListPage:
    """Return value of ``list_sources`` (D104).

    Pairs the returned sources with the optional next cursor.
    Empty page is a valid return when no sources match for the
    given tenant; the adapter returns ``sources=()`` plus
    ``next_cursor=None`` in that case.
    """

    sources: tuple[Source, ...]
    next_cursor: SourceListCursor | None


__all__ = [
    "MalformedCursorError",
    "PAGE_SIZE_CEILING",
    "SourceListCursor",
    "SourceListPage",
]
