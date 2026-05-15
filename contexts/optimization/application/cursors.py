"""Cursor codecs for the optimization read surface.

Two list shapes — recommendations and optimization runs — each with
its own cursor type and codec mirroring the run-history pattern
(base64-encoded JSON, opaque to consumers).

Encode/decode helpers live here so the future HTTP layer at S42
imports a single pair of functions per list shape; the cursor
strings survive the HTTP boundary verbatim.

Decode validates the schema and raises ``MalformedCursorError`` on
base64, JSON, schema, type, or range errors. The HTTP layer
translates to 400.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from datetime import datetime
from uuid import UUID

from contexts.optimization.domain.query_filters import (
    MalformedCursorError,
    OptimizationRunListCursor,
    RecommendationListCursor,
)


_URLSAFE_B64_ALPHABET = re.compile(r"^[A-Za-z0-9_\-]+=*$")


def encode_recommendation_cursor(cursor: RecommendationListCursor) -> str:
    payload = {
        "generated_at": cursor.generated_at.isoformat(),
        "id": str(cursor.id),
        "page_size": cursor.page_size,
    }
    return _encode(payload)


def decode_recommendation_cursor(encoded: str) -> RecommendationListCursor:
    payload = _decode(encoded)
    _require_keys(payload, ("generated_at", "id", "page_size"))
    generated_at_raw = payload["generated_at"]
    id_raw = payload["id"]
    page_size_raw = payload["page_size"]
    _require_str(generated_at_raw, "generated_at")
    _require_str(id_raw, "id")
    _require_int(page_size_raw, "page_size")

    try:
        generated_at = datetime.fromisoformat(generated_at_raw)
    except ValueError as exc:
        raise MalformedCursorError(
            f"generated_at not parseable as ISO datetime: {exc}"
        ) from exc
    try:
        cursor_id = UUID(id_raw)
    except ValueError as exc:
        raise MalformedCursorError(
            f"id not parseable as UUID: {exc}"
        ) from exc
    try:
        return RecommendationListCursor(
            generated_at=generated_at,
            id=cursor_id,
            page_size=page_size_raw,
        )
    except ValueError as exc:
        raise MalformedCursorError(str(exc)) from exc


def encode_optimization_run_cursor(cursor: OptimizationRunListCursor) -> str:
    payload = {
        "invoked_at": cursor.invoked_at.isoformat(),
        "id": str(cursor.id),
        "page_size": cursor.page_size,
    }
    return _encode(payload)


def decode_optimization_run_cursor(
    encoded: str,
) -> OptimizationRunListCursor:
    payload = _decode(encoded)
    _require_keys(payload, ("invoked_at", "id", "page_size"))
    invoked_at_raw = payload["invoked_at"]
    id_raw = payload["id"]
    page_size_raw = payload["page_size"]
    _require_str(invoked_at_raw, "invoked_at")
    _require_str(id_raw, "id")
    _require_int(page_size_raw, "page_size")

    try:
        invoked_at = datetime.fromisoformat(invoked_at_raw)
    except ValueError as exc:
        raise MalformedCursorError(
            f"invoked_at not parseable as ISO datetime: {exc}"
        ) from exc
    try:
        cursor_id = UUID(id_raw)
    except ValueError as exc:
        raise MalformedCursorError(
            f"id not parseable as UUID: {exc}"
        ) from exc
    try:
        return OptimizationRunListCursor(
            invoked_at=invoked_at,
            id=cursor_id,
            page_size=page_size_raw,
        )
    except ValueError as exc:
        raise MalformedCursorError(str(exc)) from exc


def _encode(payload: dict) -> str:
    json_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(json_bytes).decode("ascii")


def _decode(encoded: str) -> dict:
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


def _require_str(value, name: str) -> None:
    if not isinstance(value, str):
        raise MalformedCursorError(
            f"{name} must be a string; got {type(value).__name__}"
        )


def _require_int(value, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise MalformedCursorError(
            f"{name} must be an int; got {type(value).__name__}"
        )


__all__ = [
    "decode_optimization_run_cursor",
    "decode_recommendation_cursor",
    "encode_optimization_run_cursor",
    "encode_recommendation_cursor",
]
