"""Query filter and cursor value objects for the read surface (D111).

Mirrors the run-history and retrieval-evaluation cursor patterns (D97,
D110). Two list surfaces ship at commit 5:

- ``RecommendationListFilters`` carries the four-dimensional filter
  surface from the brief (category + status; agent_template_ids and
  time-range filters are forward affordance, not Phase 1 must-have)
  per D111 commitment 5's listing semantics.
- ``RecommendationListCursor`` paginates on ``(generated_at, id)``.
- ``OptimizationRunListCursor`` paginates on ``(invoked_at, id)``.
- ``MalformedCursorError`` raises at decode time so the future HTTP
  layer at S42 translates to 400 cleanly.

All cursors cap at ``PAGE_SIZE_CEILING`` (50) mirroring D97.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from contexts.optimization.domain.category import RecommendationCategory
from contexts.optimization.domain.recommendation_status import (
    RecommendationStatus,
)


PAGE_SIZE_CEILING: int = 50


class MalformedCursorError(Exception):
    """Raised when ``decode`` cannot reconstruct a cursor."""


@dataclass(frozen=True)
class RecommendationListFilters:
    """Optional filter dimensions for ``list_recommendations``.

    Both filter dimensions are multi-value; empty tuples normalise to
    ``None`` at construction so the adapter sees a consistent "no
    filter" shape regardless of caller representation.
    """

    categories: tuple[RecommendationCategory, ...] | None = None
    statuses: tuple[RecommendationStatus, ...] | None = None

    def __post_init__(self) -> None:
        if self.categories is not None and len(self.categories) == 0:
            object.__setattr__(self, "categories", None)
        if self.statuses is not None and len(self.statuses) == 0:
            object.__setattr__(self, "statuses", None)


@dataclass(frozen=True)
class RecommendationListCursor:
    """Pagination cursor on ``(generated_at, id, page_size)``."""

    generated_at: datetime
    id: UUID
    page_size: int

    def __post_init__(self) -> None:
        if not (1 <= self.page_size <= PAGE_SIZE_CEILING):
            raise ValueError(
                f"page_size must be in [1, {PAGE_SIZE_CEILING}]; "
                f"got {self.page_size}"
            )


@dataclass(frozen=True)
class OptimizationRunListCursor:
    """Pagination cursor on ``(invoked_at, id, page_size)``."""

    invoked_at: datetime
    id: UUID
    page_size: int

    def __post_init__(self) -> None:
        if not (1 <= self.page_size <= PAGE_SIZE_CEILING):
            raise ValueError(
                f"page_size must be in [1, {PAGE_SIZE_CEILING}]; "
                f"got {self.page_size}"
            )


__all__ = [
    "MalformedCursorError",
    "OptimizationRunListCursor",
    "PAGE_SIZE_CEILING",
    "RecommendationListCursor",
    "RecommendationListFilters",
]
