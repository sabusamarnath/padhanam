"""Unit tests for the optimization cursor codecs."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contexts.optimization.application.cursors import (
    decode_optimization_run_cursor,
    decode_recommendation_cursor,
    encode_optimization_run_cursor,
    encode_recommendation_cursor,
)
from contexts.optimization.domain.query_filters import (
    MalformedCursorError,
    OptimizationRunListCursor,
    RecommendationListCursor,
)


_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc)


# ----------------------------------------------------------------------
# Recommendation cursor codec
# ----------------------------------------------------------------------


def test_recommendation_cursor_round_trip() -> None:
    original = RecommendationListCursor(
        generated_at=_NOW, id=uuid4(), page_size=20
    )
    encoded = encode_recommendation_cursor(original)
    assert decode_recommendation_cursor(encoded) == original


def test_recommendation_cursor_decode_malformed_base64_raises() -> None:
    with pytest.raises(MalformedCursorError):
        decode_recommendation_cursor("not!!base64!!")


def test_recommendation_cursor_decode_missing_field_raises() -> None:
    payload = json.dumps({"id": str(uuid4()), "page_size": 20})
    encoded = base64.urlsafe_b64encode(payload.encode()).decode("ascii")
    with pytest.raises(MalformedCursorError, match="generated_at"):
        decode_recommendation_cursor(encoded)


def test_recommendation_cursor_decode_invalid_page_size_raises() -> None:
    payload = json.dumps(
        {
            "generated_at": _NOW.isoformat(),
            "id": str(uuid4()),
            "page_size": 9999,
        }
    )
    encoded = base64.urlsafe_b64encode(payload.encode()).decode("ascii")
    with pytest.raises(MalformedCursorError):
        decode_recommendation_cursor(encoded)


# ----------------------------------------------------------------------
# OptimizationRun cursor codec
# ----------------------------------------------------------------------


def test_optimization_run_cursor_round_trip() -> None:
    original = OptimizationRunListCursor(
        invoked_at=_NOW, id=uuid4(), page_size=10
    )
    encoded = encode_optimization_run_cursor(original)
    assert decode_optimization_run_cursor(encoded) == original


def test_optimization_run_cursor_decode_missing_field_raises() -> None:
    payload = json.dumps({"id": str(uuid4()), "page_size": 20})
    encoded = base64.urlsafe_b64encode(payload.encode()).decode("ascii")
    with pytest.raises(MalformedCursorError, match="invoked_at"):
        decode_optimization_run_cursor(encoded)
