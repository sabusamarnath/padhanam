"""Query filter and cursor value objects for the gold-set read surface.

Mirrors the run_history-context pattern from S33 / D97. The
``GoldSetListCursor`` carries the (created_at, id, page_size) tuple
that paginates ``list_gold_sets`` reads ordered by created_at
descending with id descending as the deterministic tiebreaker.
``MalformedCursorError`` raises at decode time on reconstruction
failure so the HTTP layer at S42 translates to 400 cleanly.

Page size ceiling is 50, matching the run_history precedent.

Domain code is framework-free per D16 — stdlib dataclasses only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


PAGE_SIZE_CEILING: int = 50


class MalformedCursorError(Exception):
    """Raised when ``decode`` cannot reconstruct a ``GoldSetListCursor``.

    Covers base64 errors, malformed JSON, missing required fields,
    wrong field types, and out-of-range ``page_size``. The HTTP layer
    at S42 translates to 400.
    """


@dataclass(frozen=True)
class GoldSetListCursor:
    """Pagination cursor for ``list_gold_sets``.

    Ordered by (created_at DESC, id DESC). The cursor points at the
    last row of the previous page; the adapter returns rows strictly
    before it. The encoded form lives at
    ``contexts/retrieval_evaluation/application/cursor.py``.
    """

    created_at: datetime
    id: UUID
    page_size: int

    def __post_init__(self) -> None:
        if self.page_size < 1 or self.page_size > PAGE_SIZE_CEILING:
            raise ValueError(
                f"page_size must be in 1..{PAGE_SIZE_CEILING}, "
                f"got {self.page_size}"
            )
