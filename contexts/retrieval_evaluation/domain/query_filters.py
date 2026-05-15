"""Query filter and cursor value objects for the retrieval-evaluation reads.

Mirrors the run_history-context pattern from S33 / D97. Two cursor
shapes share the same ``(timestamp, id, page_size)`` triple and the
same ``MalformedCursorError`` decode-failure signal:

- ``GoldSetListCursor`` paginates ``list_gold_sets`` ordered by
  ``(created_at DESC, id DESC)``.
- ``EvaluationRunListCursor`` paginates ``list_evaluation_runs``
  ordered by ``(invoked_at DESC, id DESC)``.

Page size ceiling is 50, matching the run_history precedent.

Domain code is framework-free per D16 — stdlib dataclasses only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


PAGE_SIZE_CEILING: int = 50


class MalformedCursorError(Exception):
    """Raised when ``decode`` cannot reconstruct a cursor value object.

    Shared across ``GoldSetListCursor`` and ``EvaluationRunListCursor``
    decoders. Covers base64 errors, malformed JSON, missing required
    fields, wrong field types, and out-of-range ``page_size``. The
    HTTP layer at S42 translates to 400.
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


@dataclass(frozen=True)
class EvaluationRunListCursor:
    """Pagination cursor for ``list_evaluation_runs`` (D110).

    Ordered by (invoked_at DESC, id DESC). The cursor points at the
    last row of the previous page; the adapter returns rows strictly
    before it. The encoded form lives at
    ``contexts/retrieval_evaluation/application/cursor.py``.
    """

    invoked_at: datetime
    id: UUID
    page_size: int

    def __post_init__(self) -> None:
        if self.page_size < 1 or self.page_size > PAGE_SIZE_CEILING:
            raise ValueError(
                f"page_size must be in 1..{PAGE_SIZE_CEILING}, "
                f"got {self.page_size}"
            )
