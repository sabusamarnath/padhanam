"""Cursor codec for the retrieval-evaluation read surfaces (mirrors S33 / D97).

Encode and decode ``GoldSetListCursor`` and ``EvaluationRunListCursor``
instances as base64-of-JSON opaque strings that survive the HTTP
boundary at S42. The two cursor types share the same payload shape
(``{<timestamp>, "id", "page_size"}``) and the same
``MalformedCursorError`` decode-failure signal; the timestamp field
name differs to preserve domain semantics (``created_at`` for gold
sets, ``invoked_at`` for runs).

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
    EvaluationRunListCursor,
    GoldSetListCursor,
    MalformedCursorError,
)


_URLSAFE_B64_ALPHABET = re.compile(r"^[A-Za-z0-9_\-]+=*$")


def _b64_to_payload(encoded: str) -> dict:
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
    return payload


def _payload_to_b64(payload: dict) -> str:
    json_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(json_bytes).decode("ascii")


def _read_str(payload: dict, field_name: str) -> str:
    if field_name not in payload:
        raise MalformedCursorError(
            f"cursor payload missing required field {field_name!r}"
        )
    value = payload[field_name]
    if not isinstance(value, str):
        raise MalformedCursorError(
            f"{field_name} must be a string; got {type(value).__name__}"
        )
    return value


def _read_int(payload: dict, field_name: str) -> int:
    if field_name not in payload:
        raise MalformedCursorError(
            f"cursor payload missing required field {field_name!r}"
        )
    value = payload[field_name]
    if not isinstance(value, int) or isinstance(value, bool):
        raise MalformedCursorError(
            f"{field_name} must be an int; got {type(value).__name__}"
        )
    return value


def _parse_datetime(raw: str, field_name: str) -> datetime:
    try:
        return datetime.fromisoformat(raw)
    except ValueError as exc:
        raise MalformedCursorError(
            f"{field_name} not parseable as ISO datetime: {exc}"
        ) from exc


def _parse_uuid(raw: str, field_name: str) -> UUID:
    try:
        return UUID(raw)
    except ValueError as exc:
        raise MalformedCursorError(
            f"{field_name} not parseable as UUID: {exc}"
        ) from exc


def encode(cursor: GoldSetListCursor) -> str:
    return _payload_to_b64(
        {
            "created_at": cursor.created_at.isoformat(),
            "id": str(cursor.id),
            "page_size": cursor.page_size,
        }
    )


def decode(encoded: str) -> GoldSetListCursor:
    payload = _b64_to_payload(encoded)
    created_at = _parse_datetime(_read_str(payload, "created_at"), "created_at")
    gold_set_id = _parse_uuid(_read_str(payload, "id"), "id")
    page_size = _read_int(payload, "page_size")
    try:
        return GoldSetListCursor(
            created_at=created_at, id=gold_set_id, page_size=page_size
        )
    except ValueError as exc:
        raise MalformedCursorError(str(exc)) from exc


def encode_run_cursor(cursor: EvaluationRunListCursor) -> str:
    return _payload_to_b64(
        {
            "invoked_at": cursor.invoked_at.isoformat(),
            "id": str(cursor.id),
            "page_size": cursor.page_size,
        }
    )


def decode_run_cursor(encoded: str) -> EvaluationRunListCursor:
    payload = _b64_to_payload(encoded)
    invoked_at = _parse_datetime(_read_str(payload, "invoked_at"), "invoked_at")
    run_id = _parse_uuid(_read_str(payload, "id"), "id")
    page_size = _read_int(payload, "page_size")
    try:
        return EvaluationRunListCursor(
            invoked_at=invoked_at, id=run_id, page_size=page_size
        )
    except ValueError as exc:
        raise MalformedCursorError(str(exc)) from exc


__all__ = [
    "decode",
    "decode_run_cursor",
    "encode",
    "encode_run_cursor",
]
