"""Round-trip and error tests for the audit cursor codec (D102, S36)."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from contexts.audit.application.cursor import decode, encode
from contexts.audit.domain.query_filters import (
    AuditEventListCursor,
    MalformedCursorError,
    PAGE_SIZE_CEILING,
)


# Round-trip ---------------------------------------------------------------


def test_round_trip_preserves_fields() -> None:
    cursor = AuditEventListCursor(
        timestamp=datetime(2026, 5, 14, 12, 30, 45, 123456, tzinfo=timezone.utc),
        id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        page_size=25,
    )
    decoded = decode(encode(cursor))
    assert decoded == cursor


def test_round_trip_at_page_size_ceiling() -> None:
    cursor = AuditEventListCursor(
        timestamp=datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc),
        id=uuid4(),
        page_size=PAGE_SIZE_CEILING,
    )
    decoded = decode(encode(cursor))
    assert decoded == cursor


def test_encoded_form_is_urlsafe_base64() -> None:
    cursor = AuditEventListCursor(
        timestamp=datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc),
        id=uuid4(),
        page_size=10,
    )
    encoded = encode(cursor)
    assert "+" not in encoded
    assert "/" not in encoded
    # decoding the underlying base64 yields a JSON object
    payload = json.loads(base64.urlsafe_b64decode(encoded).decode("utf-8"))
    assert set(payload.keys()) == {"timestamp", "id", "page_size"}


# Decode errors ------------------------------------------------------------


def test_decode_empty_string_raises() -> None:
    with pytest.raises(MalformedCursorError, match="base64"):
        decode("")


def test_decode_non_base64_characters_raises() -> None:
    with pytest.raises(MalformedCursorError, match="base64"):
        decode("not!valid#base64$$")


def test_decode_malformed_json_raises() -> None:
    bogus = base64.urlsafe_b64encode(b"not json").decode("ascii")
    with pytest.raises(MalformedCursorError, match="JSON"):
        decode(bogus)


def test_decode_non_object_payload_raises() -> None:
    payload = base64.urlsafe_b64encode(b"[1,2,3]").decode("ascii")
    with pytest.raises(MalformedCursorError, match="JSON object"):
        decode(payload)


@pytest.mark.parametrize("missing", ["timestamp", "id", "page_size"])
def test_decode_missing_field_raises(missing: str) -> None:
    valid_payload = {
        "timestamp": "2026-05-14T12:00:00+00:00",
        "id": str(uuid4()),
        "page_size": 25,
    }
    del valid_payload[missing]
    encoded = base64.urlsafe_b64encode(
        json.dumps(valid_payload).encode("utf-8")
    ).decode("ascii")
    with pytest.raises(MalformedCursorError, match=missing):
        decode(encoded)


def test_decode_non_string_timestamp_raises() -> None:
    payload = {
        "timestamp": 12345,
        "id": str(uuid4()),
        "page_size": 25,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload).encode("utf-8")
    ).decode("ascii")
    with pytest.raises(MalformedCursorError, match="timestamp"):
        decode(encoded)


def test_decode_non_int_page_size_raises() -> None:
    payload = {
        "timestamp": "2026-05-14T12:00:00+00:00",
        "id": str(uuid4()),
        "page_size": "25",
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload).encode("utf-8")
    ).decode("ascii")
    with pytest.raises(MalformedCursorError, match="page_size"):
        decode(encoded)


def test_decode_bool_page_size_raises() -> None:
    payload = {
        "timestamp": "2026-05-14T12:00:00+00:00",
        "id": str(uuid4()),
        "page_size": True,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload).encode("utf-8")
    ).decode("ascii")
    with pytest.raises(MalformedCursorError, match="page_size"):
        decode(encoded)


def test_decode_invalid_uuid_raises() -> None:
    payload = {
        "timestamp": "2026-05-14T12:00:00+00:00",
        "id": "not-a-uuid",
        "page_size": 25,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload).encode("utf-8")
    ).decode("ascii")
    with pytest.raises(MalformedCursorError, match="UUID"):
        decode(encoded)


def test_decode_invalid_timestamp_raises() -> None:
    payload = {
        "timestamp": "not-a-timestamp",
        "id": str(uuid4()),
        "page_size": 25,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload).encode("utf-8")
    ).decode("ascii")
    with pytest.raises(MalformedCursorError, match="timestamp"):
        decode(encoded)


def test_decode_out_of_range_page_size_raises() -> None:
    payload = {
        "timestamp": "2026-05-14T12:00:00+00:00",
        "id": str(uuid4()),
        "page_size": PAGE_SIZE_CEILING + 1,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload).encode("utf-8")
    ).decode("ascii")
    with pytest.raises(MalformedCursorError, match="page_size"):
        decode(encoded)
