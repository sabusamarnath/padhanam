"""Unit tests for the FiredTrigger value object (D147, S54)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contexts.messaging.domain.fired_trigger import FiredTrigger


def _fired_trigger(**overrides: object) -> FiredTrigger:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "tenant_id": uuid4(),
        "user_id": "operator-001",
        "trigger_type": "daily_scheduled",
        "idempotency_key": "2026-05-28",
        "fired_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return FiredTrigger(**defaults)  # type: ignore[arg-type]


def test_fired_trigger_construction() -> None:
    """A well-formed FiredTrigger constructs cleanly."""
    ft = _fired_trigger()
    assert ft.user_id == "operator-001"
    assert ft.trigger_type == "daily_scheduled"
    assert ft.idempotency_key == "2026-05-28"


def test_fired_trigger_accepts_null_idempotency_key() -> None:
    """MANUAL triggers carry a null idempotency key per D147."""
    ft = _fired_trigger(trigger_type="manual", idempotency_key=None)
    assert ft.idempotency_key is None


def test_fired_trigger_is_frozen() -> None:
    """FiredTrigger is a frozen dataclass — attribute writes fail."""
    ft = _fired_trigger()
    with pytest.raises(Exception):  # FrozenInstanceError
        ft.user_id = "operator-002"  # type: ignore[misc]


def test_fired_trigger_rejects_empty_user_id() -> None:
    with pytest.raises(ValueError, match="user_id must be non-empty"):
        _fired_trigger(user_id="")


def test_fired_trigger_rejects_empty_trigger_type() -> None:
    with pytest.raises(ValueError, match="trigger_type must be non-empty"):
        _fired_trigger(trigger_type="  ")
