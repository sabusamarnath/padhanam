"""Unit tests for the ingestion list-query parser (D104, S38).

Cover the cursor decode path and page_size defaulting, plus the
MalformedCursorError path on a bad cursor input. Mirror the audit
query-parser tests at ``test_audit_query.py``.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

import pytest

from apps.api.routers._ingestion_query import (
    MalformedCursorError,
    parse_source_list_query,
)
from contexts.ingestion.application.cursor import encode as encode_cursor
from contexts.ingestion.domain.source_list import (
    PAGE_SIZE_CEILING,
    SourceListCursor,
)


def _run(coroutine_or_value):
    """Helper: the parser is a sync function but mirrors the audit
    parser's invocation pattern for symmetry."""
    return coroutine_or_value


def test_parse_no_arguments_returns_no_cursor_and_default_page_size() -> None:
    cursor, page_size = parse_source_list_query()
    assert cursor is None
    assert page_size == PAGE_SIZE_CEILING


def test_parse_explicit_page_size() -> None:
    cursor, page_size = parse_source_list_query(page_size=10)
    assert cursor is None
    assert page_size == 10


def test_parse_decodes_valid_cursor() -> None:
    original = SourceListCursor(
        created_at=datetime(2026, 5, 14, 10, 30, tzinfo=timezone.utc),
        id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        page_size=25,
    )
    encoded = encode_cursor(original)
    cursor, page_size = parse_source_list_query(cursor=encoded, page_size=25)
    assert cursor == original
    assert page_size == 25


def test_parse_raises_malformed_cursor_error_on_bad_cursor() -> None:
    with pytest.raises(MalformedCursorError):
        parse_source_list_query(cursor="not!base64", page_size=10)
