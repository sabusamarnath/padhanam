"""Unit tests for ChainIntegrityVerification status invariants (D102, S36)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from contexts.audit.domain.chain_integrity import ChainIntegrityVerification


def test_verified_without_broken_at_id_constructs() -> None:
    verification = ChainIntegrityVerification(status="verified")
    assert verification.status == "verified"
    assert verification.broken_at_id is None


def test_partial_without_broken_at_id_constructs() -> None:
    verification = ChainIntegrityVerification(status="partial")
    assert verification.status == "partial"
    assert verification.broken_at_id is None


def test_broken_at_row_requires_broken_at_id() -> None:
    with pytest.raises(ValueError, match="broken_at_id is required"):
        ChainIntegrityVerification(status="broken_at_row")


def test_broken_at_row_with_broken_at_id_constructs() -> None:
    event_id = uuid4()
    verification = ChainIntegrityVerification(
        status="broken_at_row", broken_at_id=event_id
    )
    assert verification.status == "broken_at_row"
    assert verification.broken_at_id == event_id


def test_verified_with_broken_at_id_raises() -> None:
    with pytest.raises(ValueError, match="broken_at_id must be None"):
        ChainIntegrityVerification(status="verified", broken_at_id=uuid4())


def test_partial_with_broken_at_id_raises() -> None:
    with pytest.raises(ValueError, match="broken_at_id must be None"):
        ChainIntegrityVerification(status="partial", broken_at_id=uuid4())


def test_verification_frozen() -> None:
    verification = ChainIntegrityVerification(status="verified")
    with pytest.raises(Exception):
        verification.status = "broken_at_row"  # type: ignore[misc]
