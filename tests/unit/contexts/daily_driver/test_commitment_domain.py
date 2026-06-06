"""Unit tests for Commitment domain validation (D157)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contexts.daily_driver.domain.commitment import Commitment, OutcomeStatus


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


# --- S61 (D162): the expected-versus-observed fields ---------------


def test_outcome_fields_default_to_none() -> None:
    c = _commitment()
    assert c.expected_outcome is None
    assert c.observed_outcome is None
    assert c.outcome_status is None
    assert c.observed_at is None


def test_expected_outcome_captured_at_creation() -> None:
    c = _commitment(expected_outcome="two reports promoted this quarter")
    assert c.expected_outcome == "two reports promoted this quarter"


def test_observed_outcome_requires_status() -> None:
    with pytest.raises(ValueError, match="outcome_status must be set"):
        _commitment(observed_outcome="only one moved")


def test_observed_outcome_with_status_constructs() -> None:
    c = _commitment(
        observed_outcome="only one moved",
        outcome_status=OutcomeStatus.PARTIAL,
        observed_at=datetime(2026, 6, 6, tzinfo=timezone.utc),
    )
    assert c.outcome_status is OutcomeStatus.PARTIAL


def test_status_without_observed_text_allowed_for_drop() -> None:
    # Dropping needs no note — status alone is a valid record.
    c = _commitment(outcome_status=OutcomeStatus.DROPPED)
    assert c.outcome_status is OutcomeStatus.DROPPED
    assert c.observed_outcome is None
