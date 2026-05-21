"""Unit tests for the portfolio cursor codec (D124)."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contexts.portfolio.application.cursor import (
    decode_case_cursor,
    encode_case_cursor,
)
from contexts.portfolio.domain.query_filters import (
    CaseListCursor,
    MalformedCursorError,
)


def test_round_trip() -> None:
    cursor = CaseListCursor(
        created_at=datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc),
        id=uuid4(),
        page_size=20,
    )
    assert decode_case_cursor(encode_case_cursor(cursor)) == cursor


def test_decode_rejects_non_base64() -> None:
    with pytest.raises(MalformedCursorError):
        decode_case_cursor("not!valid!base64!")


def test_decode_rejects_missing_field() -> None:
    bad = base64.urlsafe_b64encode(
        json.dumps({"id": str(uuid4()), "page_size": 10}).encode("utf-8")
    ).decode("ascii")
    with pytest.raises(MalformedCursorError, match="created_at"):
        decode_case_cursor(bad)


def test_decode_rejects_out_of_range_page_size() -> None:
    bad = base64.urlsafe_b64encode(
        json.dumps(
            {
                "created_at": datetime(
                    2026, 5, 21, tzinfo=timezone.utc
                ).isoformat(),
                "id": str(uuid4()),
                "page_size": 999,
            }
        ).encode("utf-8")
    ).decode("ascii")
    with pytest.raises(MalformedCursorError):
        decode_case_cursor(bad)
