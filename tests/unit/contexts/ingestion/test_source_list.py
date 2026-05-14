"""Unit tests for the source-list domain value objects (D104, S38).

Cover ``SourceListCursor`` page_size validation, ``SourceListPage``
construction, and the cursor codec's encode/decode round-trip plus
its error paths. Mirror the audit cursor codec tests at
``tests/unit/contexts/audit/test_cursor.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest

from contexts.ingestion.application.cursor import decode, encode
from contexts.ingestion.domain.source_list import (
    PAGE_SIZE_CEILING,
    MalformedCursorError,
    SourceListCursor,
    SourceListPage,
)


# --------------------------------------------------------------------
# SourceListCursor.
# --------------------------------------------------------------------


def _cursor(page_size: int = 50) -> SourceListCursor:
    return SourceListCursor(
        created_at=datetime(2026, 5, 14, 10, 30, tzinfo=timezone.utc),
        id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        page_size=page_size,
    )


def test_source_list_cursor_validates_page_size_floor() -> None:
    with pytest.raises(ValueError, match="page_size must be in"):
        _cursor(page_size=0)


def test_source_list_cursor_validates_page_size_ceiling() -> None:
    with pytest.raises(ValueError, match="page_size must be in"):
        _cursor(page_size=PAGE_SIZE_CEILING + 1)


def test_source_list_cursor_accepts_page_size_at_ceiling() -> None:
    cursor = _cursor(page_size=PAGE_SIZE_CEILING)
    assert cursor.page_size == PAGE_SIZE_CEILING


def test_source_list_cursor_accepts_page_size_at_floor() -> None:
    cursor = _cursor(page_size=1)
    assert cursor.page_size == 1


# --------------------------------------------------------------------
# SourceListPage.
# --------------------------------------------------------------------


def test_source_list_page_empty_construction() -> None:
    page = SourceListPage(sources=(), next_cursor=None)
    assert page.sources == ()
    assert page.next_cursor is None


# --------------------------------------------------------------------
# Cursor codec.
# --------------------------------------------------------------------


def test_cursor_round_trip_preserves_fields() -> None:
    cursor = _cursor(page_size=25)
    encoded = encode(cursor)
    decoded = decode(encoded)
    assert decoded == cursor


def test_cursor_decode_rejects_empty_string() -> None:
    with pytest.raises(MalformedCursorError, match="non-url-safe-base64"):
        decode("")


def test_cursor_decode_rejects_non_base64_alphabet() -> None:
    with pytest.raises(MalformedCursorError, match="non-url-safe-base64"):
        decode("not!base64@")


def test_cursor_decode_rejects_non_json_payload() -> None:
    import base64

    encoded = base64.urlsafe_b64encode(b"not json").decode("ascii")
    with pytest.raises(MalformedCursorError, match="JSON decode failed"):
        decode(encoded)


def test_cursor_decode_rejects_non_object_payload() -> None:
    import base64

    encoded = base64.urlsafe_b64encode(b'"a string"').decode("ascii")
    with pytest.raises(MalformedCursorError, match="must be a JSON object"):
        decode(encoded)


def test_cursor_decode_rejects_missing_field() -> None:
    import base64
    import json

    payload = json.dumps({"created_at": "2026-05-14T10:00:00+00:00", "id": "550e8400-e29b-41d4-a716-446655440000"}).encode()
    encoded = base64.urlsafe_b64encode(payload).decode("ascii")
    with pytest.raises(MalformedCursorError, match="missing required field 'page_size'"):
        decode(encoded)


def test_cursor_decode_rejects_wrong_type_page_size() -> None:
    import base64
    import json

    payload = json.dumps(
        {
            "created_at": "2026-05-14T10:00:00+00:00",
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "page_size": "50",
        }
    ).encode()
    encoded = base64.urlsafe_b64encode(payload).decode("ascii")
    with pytest.raises(MalformedCursorError, match="page_size must be an int"):
        decode(encoded)


def test_cursor_decode_rejects_out_of_range_page_size() -> None:
    import base64
    import json

    payload = json.dumps(
        {
            "created_at": "2026-05-14T10:00:00+00:00",
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "page_size": 999,
        }
    ).encode()
    encoded = base64.urlsafe_b64encode(payload).decode("ascii")
    with pytest.raises(MalformedCursorError, match="page_size must be in"):
        decode(encoded)


def test_cursor_decode_rejects_invalid_uuid() -> None:
    import base64
    import json

    payload = json.dumps(
        {
            "created_at": "2026-05-14T10:00:00+00:00",
            "id": "not-a-uuid",
            "page_size": 50,
        }
    ).encode()
    encoded = base64.urlsafe_b64encode(payload).decode("ascii")
    with pytest.raises(MalformedCursorError, match="id not parseable as UUID"):
        decode(encoded)


def test_cursor_decode_rejects_invalid_datetime() -> None:
    import base64
    import json

    payload = json.dumps(
        {
            "created_at": "not-a-datetime",
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "page_size": 50,
        }
    ).encode()
    encoded = base64.urlsafe_b64encode(payload).decode("ascii")
    with pytest.raises(MalformedCursorError, match="created_at not parseable"):
        decode(encoded)
