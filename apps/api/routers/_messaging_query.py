"""Query-string parser for the messaging list endpoint (D129).

Maps the query parameters on ``GET /api/v1/messaging/messages`` to
the domain value objects ``list_messages`` consumes:

- ``direction`` (repeated) -> ``MessageListFilters.directions``
- ``channel`` (repeated) -> ``MessageListFilters.channels``
- ``cursor`` (opaque base64 string) -> decoded ``MessageListCursor`` or None
- ``page_size`` (int 1..PAGE_SIZE_CEILING)

An unknown ``direction`` / ``channel`` raises
``InvalidMessagingFilterError`` (400 ``invalid_messaging_filter``); a
malformed ``cursor`` raises the messaging ``MalformedCursorError``
(400 ``malformed_messaging_cursor``); out-of-range ``page_size`` is
caught by FastAPI's ``ge`` / ``le`` (422).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Query

from contexts.messaging.application.cursor import decode_message_cursor
from contexts.messaging.domain import MessageChannel, MessageDirection
from contexts.messaging.domain.query_filters import (
    PAGE_SIZE_CEILING,
    MessageListCursor,
    MessageListFilters,
)


class InvalidMessagingFilterError(ValueError):
    """Raised when a ``GET /messaging/messages`` filter value is unknown.

    Translates to 400 ``invalid_messaging_filter`` via the registered
    handler at ``apps/api/_messaging_errors.py``.
    """


def parse_message_list_query(
    direction: Annotated[list[str] | None, Query()] = None,
    channel: Annotated[list[str] | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_CEILING)] = 20,
) -> tuple[MessageListFilters, MessageListCursor | None, int]:
    """Parse the query string into ``(filters, cursor, page_size)``."""
    filters = MessageListFilters(
        directions=_parse_directions(direction),
        channels=_parse_channels(channel),
    )
    decoded = decode_message_cursor(cursor) if cursor is not None else None
    return filters, decoded, page_size


def _parse_directions(
    raw: list[str] | None,
) -> tuple[MessageDirection, ...] | None:
    if not raw:
        return None
    parsed: list[MessageDirection] = []
    for value in raw:
        try:
            parsed.append(MessageDirection(value))
        except ValueError as exc:
            valid = ", ".join(d.value for d in MessageDirection)
            raise InvalidMessagingFilterError(
                f"unknown direction {value!r}; valid values: {valid}"
            ) from exc
    return tuple(parsed)


def _parse_channels(
    raw: list[str] | None,
) -> tuple[MessageChannel, ...] | None:
    if not raw:
        return None
    parsed: list[MessageChannel] = []
    for value in raw:
        try:
            parsed.append(MessageChannel(value))
        except ValueError as exc:
            valid = ", ".join(c.value for c in MessageChannel)
            raise InvalidMessagingFilterError(
                f"unknown channel {value!r}; valid values: {valid}"
            ) from exc
    return tuple(parsed)


__all__ = ["InvalidMessagingFilterError", "parse_message_list_query"]
