"""Query filter and cursor value objects for the messaging list surface (D129).

Mirrors the intake query-filter pattern. ``list_messages`` is the
one paginated messaging surface; it carries optional multi-value
direction and channel filters and a cursor paginating on
``(created_at, id, page_size)``.

``MalformedCursorError`` raises at decode time so the HTTP layer
translates to 400. Cursors cap at ``PAGE_SIZE_CEILING`` (50).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from contexts.messaging.domain.message import MessageChannel, MessageDirection

PAGE_SIZE_CEILING: int = 50


class MalformedCursorError(Exception):
    """Raised when ``decode`` cannot reconstruct a message cursor."""


@dataclass(frozen=True)
class MessageListFilters:
    """Optional filter dimensions for ``list_messages``.

    Both dimensions are multi-value; an empty tuple normalises to
    ``None`` at construction so the adapter sees a consistent "no
    filter" shape.
    """

    directions: tuple[MessageDirection, ...] | None = None
    channels: tuple[MessageChannel, ...] | None = None

    def __post_init__(self) -> None:
        if self.directions is not None and len(self.directions) == 0:
            object.__setattr__(self, "directions", None)
        if self.channels is not None and len(self.channels) == 0:
            object.__setattr__(self, "channels", None)


@dataclass(frozen=True)
class MessageListCursor:
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
    "MalformedCursorError",
    "MessageListCursor",
    "MessageListFilters",
    "PAGE_SIZE_CEILING",
]
