"""Query filter and cursor value objects for the portfolio read surface (D124).

Mirrors the optimization and run-history cursor patterns (D97, D111).
``list_cases`` is the one paginated surface at S43; data-point and
assertion lists are bounded per parent and return unpaginated.

- ``CaseListFilters`` carries the optional case_type + status filter
  dimensions, both multi-value.
- ``CaseListCursor`` paginates on ``(created_at, id, page_size)``.
- ``MalformedCursorError`` raises at decode time so the HTTP layer
  translates to 400.

Cursors cap at ``PAGE_SIZE_CEILING`` (50) mirroring D97.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from contexts.portfolio.domain.case import CaseStatus, CaseType

PAGE_SIZE_CEILING: int = 50


class MalformedCursorError(Exception):
    """Raised when ``decode`` cannot reconstruct a cursor."""


@dataclass(frozen=True)
class CaseListFilters:
    """Optional filter dimensions for ``list_cases``.

    Both dimensions are multi-value; empty tuples normalise to
    ``None`` at construction so the adapter sees a consistent
    "no filter" shape.
    """

    case_types: tuple[CaseType, ...] | None = None
    statuses: tuple[CaseStatus, ...] | None = None

    def __post_init__(self) -> None:
        if self.case_types is not None and len(self.case_types) == 0:
            object.__setattr__(self, "case_types", None)
        if self.statuses is not None and len(self.statuses) == 0:
            object.__setattr__(self, "statuses", None)


@dataclass(frozen=True)
class CaseListCursor:
    """Pagination cursor on ``(created_at, id, page_size)``."""

    created_at: datetime
    id: UUID
    page_size: int

    def __post_init__(self) -> None:
        if not 1 <= self.page_size <= PAGE_SIZE_CEILING:
            raise ValueError(
                f"page_size must be in [1, {PAGE_SIZE_CEILING}]; "
                f"got {self.page_size}"
            )


__all__ = [
    "CaseListCursor",
    "CaseListFilters",
    "MalformedCursorError",
    "PAGE_SIZE_CEILING",
]
