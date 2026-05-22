"""Cursor codec for the messaging list surface (D129).

Base64-encoded JSON, opaque to consumers, mirroring the intake
cursor pattern. ``list_messages`` is the one paginated messaging
surface; the codec round-trips ``MessageListCursor`` across the
HTTP boundary verbatim.

Decode validates the schema and raises ``MalformedCursorError`` on
base64, JSON, schema, type, or range errors.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from datetime import datetime
from uuid import UUID

from contexts.messaging.domain.query_filters import (
    MalformedCursorError,
    MessageListCursor,
)

_URLSAFE_B64_ALPHABET = re.compile(r"^[A-Za-z0-9_\-]+=*$")


def encode_message_cursor(cursor: MessageListCursor) -> str:
    return _encode(
        {
            "created_at": cursor.created_at.isoformat(),
            "id": str(cursor.id),
            "page_size": cursor.page_size,
        }
    )


def decode_message_cursor(encoded: str) -> MessageListCursor:
    payload = _decode(encoded)
    _require_keys(payload, ("created_at", "id", "page_size"))
    created_at_raw = payload["created_at"]
    id_raw = payload["id"]
    page_size_raw = payload["page_size"]
    _require_str(created_at_raw, "created_at")
    _require_str(id_raw, "id")
    _require_int(page_size_raw, "page_size")

    try:
        created_at = datetime.fromisoformat(created_at_raw)
    except ValueError as exc:
        raise MalformedCursorError(
            f"created_at not parseable as ISO datetime: {exc}"
        ) from exc
    try:
        cursor_id = UUID(id_raw)
    except ValueError as exc:
        raise MalformedCursorError(
            f"id not parseable as UUID: {exc}"
        ) from exc
    try:
        return MessageListCursor(
            created_at=created_at, id=cursor_id, page_size=page_size_raw
        )
    except ValueError as exc:
        raise MalformedCursorError(str(exc)) from exc


def _encode(payload: dict) -> str:
    json_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(json_bytes).decode("ascii")


def _decode(encoded: str) -> dict:
    if not encoded or not _URLSAFE_B64_ALPHABET.match(encoded):
        raise MalformedCursorError(
            "base64 decode failed: input contains non-url-safe-base64 "
            "characters"
        )
    try:
        json_bytes = base64.urlsafe_b64decode(encoded.encode("ascii"))
    except (binascii.Error, ValueError, UnicodeEncodeError) as exc:
        raise MalformedCursorError(f"base64 decode failed: {exc}") from exc
    try:
        payload = json.loads(json_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise MalformedCursorError(f"JSON decode failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise MalformedCursorError(
            f"cursor payload must be a JSON object; "
            f"got {type(payload).__name__}"
        )
    return payload


def _require_keys(payload: dict, keys: tuple[str, ...]) -> None:
    for field_name in keys:
        if field_name not in payload:
            raise MalformedCursorError(
                f"cursor payload missing required field {field_name!r}"
            )


def _require_str(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise MalformedCursorError(
            f"{name} must be a string; got {type(value).__name__}"
        )


def _require_int(value: object, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise MalformedCursorError(
            f"{name} must be an int; got {type(value).__name__}"
        )


__all__ = ["decode_message_cursor", "encode_message_cursor"]
