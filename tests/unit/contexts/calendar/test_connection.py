"""Unit tests for the calendar Connection value object (D148)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from contexts.calendar.domain.connection import Connection

_NOW = datetime(2026, 5, 28, 12, 0, 0, tzinfo=timezone.utc)


def _connection(**overrides: object) -> Connection:
    base: dict[str, object] = {
        "id": uuid4(),
        "tenant_id": uuid4(),
        "jurisdiction": "eu-west",
        "provider": "google_calendar",
        "provider_config_key": "google-calendar",
        "provider_connection_ref": "d46195b2-ad85-4d1c-a876-b978b9347ccd",
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    base.update(overrides)
    return Connection(**base)  # type: ignore[arg-type]


def test_connection_holds_opaque_provider_reference() -> None:
    conn = _connection()
    assert conn.provider_connection_ref == "d46195b2-ad85-4d1c-a876-b978b9347ccd"
    assert conn.provider_config_key == "google-calendar"
    assert conn.provider == "google_calendar"


@pytest.mark.parametrize("field", ["jurisdiction", "provider", "provider_config_key"])
def test_empty_required_string_rejected(field: str) -> None:
    with pytest.raises(ValueError):
        _connection(**{field: "   "})


def test_empty_connection_ref_rejected() -> None:
    with pytest.raises(ValueError, match="provider_connection_ref"):
        _connection(provider_connection_ref="")


def test_updated_before_created_rejected() -> None:
    with pytest.raises(ValueError, match="updated_at"):
        _connection(updated_at=_NOW - timedelta(seconds=1))
