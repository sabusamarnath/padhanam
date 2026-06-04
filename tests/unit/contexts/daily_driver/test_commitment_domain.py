"""Unit tests for Commitment domain validation (D157)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contexts.daily_driver.domain.commitment import Commitment


def _commitment(**overrides: object) -> Commitment:
    base: dict[str, object] = dict(
        id=uuid4(),
        tenant_id=uuid4(),
        jurisdiction="eu-west",
        name="Weekly review",
        expected_interval_days=7,
        authored_by_user_id="operator",
        created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return Commitment(**base)  # type: ignore[arg-type]


def test_valid_commitment_constructs() -> None:
    assert _commitment().expected_interval_days == 7


def test_empty_name_rejected() -> None:
    with pytest.raises(ValueError, match="name must be non-empty"):
        _commitment(name="  ")


def test_non_positive_interval_rejected() -> None:
    with pytest.raises(ValueError, match="expected_interval_days must be positive"):
        _commitment(expected_interval_days=0)


def test_empty_jurisdiction_rejected() -> None:
    with pytest.raises(ValueError, match="jurisdiction must be non-empty"):
        _commitment(jurisdiction="")
