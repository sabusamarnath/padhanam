"""Unit tests for the cursor encode/decode codec (D97, S33).

Covers round-trip equality, base64/JSON malformations, missing
fields, wrong types, and out-of-range values caught by
RunListCursor's __post_init__ surfacing as MalformedCursorError.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from uuid import UUID

import pytest

from contexts.run_history.application.cursor import decode, encode
from contexts.run_history.domain.query_filters import (
    MalformedCursorError,
    RunListCursor,
)


_KNOWN_UUID = UUID("550e8400-e29b-41d4-a716-446655440000")
_KNOWN_AT = datetime(2026, 5, 13, 10, 30, 0, 123456, tzinfo=timezone.utc)


def _make_cursor(
    *,
    started_at: datetime = _KNOWN_AT,
    id: UUID = _KNOWN_UUID,
    page_size: int = 50,
) -> RunListCursor:
    return RunListCursor(started_at=started_at, id=id, page_size=page_size)


def _b64(payload: dict | bytes) -> str:
    if isinstance(payload, dict):
        payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


# --------------------------------------------------------------------
# Round-trip and stability.
# --------------------------------------------------------------------


def test_encode_decode_round_trip() -> None:
    cursor = _make_cursor()
    encoded = encode(cursor)
    decoded = decode(encoded)
    assert decoded == cursor


def test_encode_produces_url_safe_base64() -> None:
    """No '+' or '/' or '=' padding in the canonical case (urlsafe alphabet)."""
    cursor = _make_cursor()
    encoded = encode(cursor)
    # urlsafe alphabet may produce '-' and '_' but not '+' or '/'.
    assert "+" not in encoded
    assert "/" not in encoded


def test_encode_deterministic_for_same_input() -> None:
    """Same cursor produces same encoded string each call."""
    cursor = _make_cursor()
    assert encode(cursor) == encode(cursor)


def test_encode_decode_round_trip_at_page_size_boundaries() -> None:
    for ps in (1, 25, 50):
        cursor = _make_cursor(page_size=ps)
        assert decode(encode(cursor)) == cursor


def test_round_trip_preserves_microseconds_on_started_at() -> None:
    cursor = _make_cursor(started_at=datetime(2026, 5, 13, 10, 30, 0, 987654, tzinfo=timezone.utc))
    decoded = decode(encode(cursor))
    assert decoded.started_at == cursor.started_at


# --------------------------------------------------------------------
# Malformed-input cases.
# --------------------------------------------------------------------


def test_decode_raises_on_malformed_base64() -> None:
    with pytest.raises(MalformedCursorError, match="base64"):
        decode("not%%%-valid-base64!!!")


def test_decode_raises_on_malformed_json_inside_base64() -> None:
    encoded = base64.urlsafe_b64encode(b"this-is-not-json").decode("ascii")
    with pytest.raises(MalformedCursorError, match="JSON"):
        decode(encoded)


def test_decode_raises_when_payload_is_not_an_object() -> None:
    encoded = _b64(b"[1, 2, 3]")
    with pytest.raises(MalformedCursorError, match="JSON object"):
        decode(encoded)


def test_decode_raises_when_started_at_missing() -> None:
    encoded = _b64({"id": str(_KNOWN_UUID), "page_size": 50})
    with pytest.raises(MalformedCursorError, match="started_at"):
        decode(encoded)


def test_decode_raises_when_id_missing() -> None:
    encoded = _b64({"started_at": _KNOWN_AT.isoformat(), "page_size": 50})
    with pytest.raises(MalformedCursorError, match="'id'"):
        decode(encoded)


def test_decode_raises_when_page_size_missing() -> None:
    encoded = _b64({"started_at": _KNOWN_AT.isoformat(), "id": str(_KNOWN_UUID)})
    with pytest.raises(MalformedCursorError, match="page_size"):
        decode(encoded)


def test_decode_raises_when_started_at_wrong_type() -> None:
    encoded = _b64({"started_at": 12345, "id": str(_KNOWN_UUID), "page_size": 50})
    with pytest.raises(MalformedCursorError, match="started_at"):
        decode(encoded)


def test_decode_raises_when_id_wrong_type() -> None:
    encoded = _b64({"started_at": _KNOWN_AT.isoformat(), "id": 12345, "page_size": 50})
    with pytest.raises(MalformedCursorError, match="id"):
        decode(encoded)


def test_decode_raises_when_page_size_wrong_type() -> None:
    encoded = _b64({"started_at": _KNOWN_AT.isoformat(), "id": str(_KNOWN_UUID), "page_size": "50"})
    with pytest.raises(MalformedCursorError, match="page_size"):
        decode(encoded)


def test_decode_rejects_bool_disguised_as_int_for_page_size() -> None:
    """In Python ``bool`` is a subclass of ``int``; the codec rejects bool
    explicitly so True/False cannot pose as page_size."""
    encoded = _b64({"started_at": _KNOWN_AT.isoformat(), "id": str(_KNOWN_UUID), "page_size": True})
    with pytest.raises(MalformedCursorError, match="page_size"):
        decode(encoded)


def test_decode_raises_on_unparseable_started_at() -> None:
    encoded = _b64({"started_at": "not-a-date", "id": str(_KNOWN_UUID), "page_size": 50})
    with pytest.raises(MalformedCursorError, match="ISO datetime"):
        decode(encoded)


def test_decode_raises_on_unparseable_uuid() -> None:
    encoded = _b64({"started_at": _KNOWN_AT.isoformat(), "id": "not-a-uuid", "page_size": 50})
    with pytest.raises(MalformedCursorError, match="UUID"):
        decode(encoded)


def test_decode_raises_when_page_size_out_of_range() -> None:
    """page_size validation flows through RunListCursor.__post_init__
    surfacing as MalformedCursorError per the codec contract."""
    encoded = _b64({"started_at": _KNOWN_AT.isoformat(), "id": str(_KNOWN_UUID), "page_size": 0})
    with pytest.raises(MalformedCursorError, match="page_size"):
        decode(encoded)

    encoded_high = _b64({"started_at": _KNOWN_AT.isoformat(), "id": str(_KNOWN_UUID), "page_size": 9999})
    with pytest.raises(MalformedCursorError, match="page_size"):
        decode(encoded_high)
