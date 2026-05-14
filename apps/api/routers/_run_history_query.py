"""Query-string parser for the run-history list endpoint (D98, S34).

Maps the six query parameters on ``GET /runs`` to the domain value
objects the reader port consumes:

- ``agent_template_id`` (repeated) -> ``RunListFilters.agent_template_ids``
- ``agent_template_version`` (repeated) -> ``RunListFilters.agent_template_versions``
- ``started_at_after`` + ``started_at_before`` (paired) -> ``RunListFilters.started_at_range``
- ``termination_reason`` (repeated) -> ``RunListFilters.termination_reasons``
- ``cursor`` (opaque base64 string) -> decoded ``RunListCursor`` or None
- ``page_size`` (int 1..PAGE_SIZE_CEILING) -> threaded into the cursor

Empty repeated params and ``None`` both collapse to ``None`` (no-filter)
per the S33 ``RunListFilters`` invariant.

The parser raises:

- ``InvalidFilterRangeError`` when ``started_at_after`` and
  ``started_at_before`` are not both provided, or when the lower bound
  is not strictly earlier than the upper bound.
- ``MalformedCursorError`` (re-raised from the domain codec) when
  ``cursor`` cannot be decoded.

Page-size threading on the initial page (cursor=None) uses a sentinel
cursor with max-representable ``started_at`` and ``id`` so the adapter's
``WHERE (started_at, id) < (cursor.started_at, cursor.id)`` clause is
trivially satisfied for every real row, while the cursor's
``page_size`` field carries the user-requested value into the
adapter's ``LIMIT page_size + 1`` step. The alternative (extending the
reader port to accept a separate ``page_size`` parameter) would
duplicate the cursor's existing role; the sentinel-cursor approach
keeps the port surface unchanged.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Query

from contexts.run_history.application.cursor import decode as decode_cursor
from contexts.run_history.domain.query_filters import (
    PAGE_SIZE_CEILING,
    MalformedCursorError,
    RunListCursor,
    RunListFilters,
)


class InvalidFilterRangeError(ValueError):
    """Raised when started_at_after / started_at_before are mismatched.

    Either only one was supplied, or the lower bound is not strictly
    earlier than the upper bound. The HTTP exception handler translates
    to 400 with code ``invalid_filter_range``.
    """


# Sentinel values for the initial-page synthetic cursor. The values
# carry no semantic meaning beyond "comparison against any real row
# is true"; the adapter's row-tuple comparison treats them as upper
# bounds in (started_at, id) tuple order.
_SENTINEL_STARTED_AT = datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)
_SENTINEL_ID = UUID(int=(1 << 128) - 1)


def parse_run_list_query(
    agent_template_id: Annotated[list[UUID] | None, Query()] = None,
    agent_template_version: Annotated[list[int] | None, Query()] = None,
    started_at_after: Annotated[datetime | None, Query()] = None,
    started_at_before: Annotated[datetime | None, Query()] = None,
    termination_reason: Annotated[list[str] | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    page_size: Annotated[int | None, Query(ge=1, le=PAGE_SIZE_CEILING)] = None,
) -> tuple[RunListFilters, RunListCursor | None]:
    """Parse query-string into ``(RunListFilters, RunListCursor | None)``.

    FastAPI invokes this as a sub-dependency of the ``GET /runs`` route
    via ``Depends(parse_run_list_query)``. Validation failures raise
    ``InvalidFilterRangeError`` (400) or ``MalformedCursorError`` (400);
    out-of-range ``page_size`` is caught earlier by FastAPI's ``ge`` /
    ``le`` (422).
    """
    started_at_range = _validate_date_range(started_at_after, started_at_before)

    filters = RunListFilters(
        agent_template_ids=tuple(agent_template_id) if agent_template_id else None,
        agent_template_versions=(
            tuple(agent_template_version) if agent_template_version else None
        ),
        started_at_range=started_at_range,
        termination_reasons=tuple(termination_reason) if termination_reason else None,
    )

    resolved_cursor = _resolve_cursor(cursor=cursor, page_size=page_size)
    return filters, resolved_cursor


def _validate_date_range(
    started_at_after: datetime | None,
    started_at_before: datetime | None,
) -> tuple[datetime, datetime] | None:
    """Map the paired date params into RunListFilters.started_at_range."""
    if started_at_after is None and started_at_before is None:
        return None
    if started_at_after is None or started_at_before is None:
        raise InvalidFilterRangeError(
            "started_at_after and started_at_before must both be provided "
            "or both omitted; got "
            f"started_at_after={started_at_after!r} "
            f"started_at_before={started_at_before!r}"
        )
    if started_at_after >= started_at_before:
        raise InvalidFilterRangeError(
            "started_at_after must be strictly earlier than started_at_before; "
            f"got started_at_after={started_at_after.isoformat()} "
            f"started_at_before={started_at_before.isoformat()}"
        )
    return (started_at_after, started_at_before)


def _resolve_cursor(
    *,
    cursor: str | None,
    page_size: int | None,
) -> RunListCursor | None:
    """Build the effective ``RunListCursor`` from query inputs.

    Four cases:

    1. cursor=None, page_size=None: return None; adapter uses
       PAGE_SIZE_CEILING.
    2. cursor=None, page_size=X: synthetic max-value cursor with
       page_size=X so the first page can carry the user's requested
       size.
    3. cursor=opaque, page_size=None: decode the cursor and use its
       embedded page_size.
    4. cursor=opaque, page_size=X: decode the cursor; page_size query
       param is ignored on subsequent pages (the cursor's embedded
       page_size is authoritative once pagination has started).
    """
    if cursor is None:
        if page_size is None:
            return None
        return RunListCursor(
            started_at=_SENTINEL_STARTED_AT,
            id=_SENTINEL_ID,
            page_size=page_size,
        )
    return decode_cursor(cursor)


__all__ = [
    "InvalidFilterRangeError",
    "MalformedCursorError",
    "parse_run_list_query",
]
