"""Query filter and cursor value objects for the intake list surface (D127).

Mirrors the portfolio query-filter pattern. ``list_intakes`` is the
one paginated intake surface; it carries an optional multi-value
intake-source filter and a cursor paginating on
``(created_at, id, page_size)``.

``MalformedCursorError`` raises at decode time so the HTTP layer
translates to 400. Cursors cap at ``PAGE_SIZE_CEILING`` (50).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from contexts.intake.domain.intake_record import IntakeSource

PAGE_SIZE_CEILING: int = 50


class MalformedCursorError(Exception):
    """Raised when ``decode`` cannot reconstruct an intake cursor."""


@dataclass(frozen=True)
class IntakeListFilters:
    """Optional filter dimensions for ``list_intakes``.

    The intake-source dimension is multi-value; an empty tuple
    normalises to ``None`` at construction so the adapter sees a
    consistent "no filter" shape.
    """

    intake_sources: tuple[IntakeSource, ...] | None = None

    def __post_init__(self) -> None:
        if self.intake_sources is not None and len(self.intake_sources) == 0:
            object.__setattr__(self, "intake_sources", None)


@dataclass(frozen=True)
class IntakeListCursor:
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
    "IntakeListCursor",
    "IntakeListFilters",
    "MalformedCursorError",
    "PAGE_SIZE_CEILING",
]
