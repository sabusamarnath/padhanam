"""Cursor codec for the gold-set read surface (mirrors S33 / D97).

Encode and decode ``GoldSetListCursor`` instances as base64-of-JSON
opaque strings that survive the HTTP boundary at S42.

    {"created_at": "2026-05-15T12:00:00.000000+00:00",
     "id": "550e8400-e29b-41d4-a716-446655440000",
     "page_size": 50}

Decode validates schema and raises ``MalformedCursorError`` on
base64, JSON, schema, type, or range errors.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from datetime import datetime
from uuid import UUID

from contexts.retrieval_evaluation.domain.query_filters import (
    GoldSetListCursor,
    MalformedCursorError,
)


_URLSAFE_B64_ALPHABET = re.compile(r"^[A-Za-z0-9_\-]+=*$")


def encode(cursor: GoldSetListCursor) -> str:
    payload = {
        "created_at": cursor.created_at.isoformat(),
        "id": str(cursor.id),
        "page_size": cursor.page_size,
    }
    json_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(json_bytes).decode("ascii")


def decode(encoded: str) -> GoldSetListCursor:
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

    for field_name in ("created_at", "id", "page_size"):
        if field_name not in payload:
            raise MalformedCursorError(
                f"cursor payload missing required field {field_name!r}"
            )

    created_at_raw = payload["created_at"]
    id_raw = payload["id"]
    page_size_raw = payload["page_size"]

    if not isinstance(created_at_raw, str):
        raise MalformedCursorError(
            f"created_at must be a string; got {type(created_at_raw).__name__}"
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
        created_at = datetime.fromisoformat(created_at_raw)
    except ValueError as exc:
        raise MalformedCursorError(
            f"created_at not parseable as ISO datetime: {exc}"
        ) from exc

    try:
        gold_set_id = UUID(id_raw)
    except ValueError as exc:
        raise MalformedCursorError(f"id not parseable as UUID: {exc}") from exc

    try:
        return GoldSetListCursor(
            created_at=created_at,
            id=gold_set_id,
            page_size=page_size_raw,
        )
    except ValueError as exc:
        raise MalformedCursorError(str(exc)) from exc


__all__ = ["decode", "encode"]
