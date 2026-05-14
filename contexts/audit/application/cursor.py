"""Cursor codec for the audit-event read surface (D102, S36).

Encode and decode ``AuditEventListCursor`` instances as opaque
strings that survive the HTTP boundary at S37. Mirror of
``contexts.run_history.application.cursor`` — base64-of-JSON per
D102's choice text:

    {"timestamp": "2026-05-13T10:30:00.000000+00:00",
     "id": "550e8400-e29b-41d4-a716-446655440000",
     "page_size": 50}

The base64 layer keeps the cursor URL-safe for HTTP query-string
or path-parameter use; the JSON layer carries the structured
shape decode reconstructs from. The cursor is opaque to
consumers: they receive an encoded string at ``next_cursor``
time and pass it back verbatim on the next request.

Decode validates the schema and raises ``MalformedCursorError``
on base64, JSON, schema, type, or range errors. The HTTP layer
at S37 catches the error and returns 400.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from datetime import datetime
from uuid import UUID

from contexts.audit.domain.query_filters import (
    AuditEventListCursor,
    MalformedCursorError,
)


_URLSAFE_B64_ALPHABET = re.compile(r"^[A-Za-z0-9_\-]+=*$")


def encode(cursor: AuditEventListCursor) -> str:
    """Encode an ``AuditEventListCursor`` as a base64-of-JSON string."""
    payload = {
        "timestamp": cursor.timestamp.isoformat(),
        "id": str(cursor.id),
        "page_size": cursor.page_size,
    }
    json_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(json_bytes).decode("ascii")


def decode(encoded: str) -> AuditEventListCursor:
    """Reconstruct an ``AuditEventListCursor`` from an opaque string.

    Raises ``MalformedCursorError`` on any reconstruction failure:
    base64 errors, JSON errors, missing fields, wrong types, or
    out-of-range ``page_size`` values caught by the cursor's own
    ``__post_init__``.
    """
    if not encoded or not _URLSAFE_B64_ALPHABET.match(encoded):
        raise MalformedCursorError(
            "base64 decode failed: input contains non-url-safe-base64 characters"
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
            f"cursor payload must be a JSON object; got {type(payload).__name__}"
        )

    for field_name in ("timestamp", "id", "page_size"):
        if field_name not in payload:
            raise MalformedCursorError(
                f"cursor payload missing required field {field_name!r}"
            )

    timestamp_raw = payload["timestamp"]
    id_raw = payload["id"]
    page_size_raw = payload["page_size"]

    if not isinstance(timestamp_raw, str):
        raise MalformedCursorError(
            f"timestamp must be a string; got {type(timestamp_raw).__name__}"
        )
    if not isinstance(id_raw, str):
        raise MalformedCursorError(
            f"id must be a string; got {type(id_raw).__name__}"
        )
    if not isinstance(page_size_raw, int) or isinstance(page_size_raw, bool):
        raise MalformedCursorError(
            f"page_size must be an int; got {type(page_size_raw).__name__}"
        )

    try:
        timestamp = datetime.fromisoformat(timestamp_raw)
    except ValueError as exc:
        raise MalformedCursorError(
            f"timestamp not parseable as ISO datetime: {exc}"
        ) from exc

    try:
        event_id = UUID(id_raw)
    except ValueError as exc:
        raise MalformedCursorError(f"id not parseable as UUID: {exc}") from exc

    try:
        return AuditEventListCursor(
            timestamp=timestamp,
            id=event_id,
            page_size=page_size_raw,
        )
    except ValueError as exc:
        raise MalformedCursorError(str(exc)) from exc


__all__ = ["decode", "encode"]
