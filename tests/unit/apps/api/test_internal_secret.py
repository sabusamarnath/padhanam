"""Unit tests for internal-secret authentication (D145, D147, S54)."""

from __future__ import annotations

import pytest

from apps.api._internal_secret import InternalSecretError, verify_internal_secret


def test_valid_secret_passes() -> None:
    verify_internal_secret(presented="s3cret", configured="s3cret")


def test_missing_header_raises() -> None:
    with pytest.raises(InternalSecretError, match="missing X-Internal-Secret"):
        verify_internal_secret(presented=None, configured="s3cret")


def test_empty_configured_secret_fails_closed() -> None:
    """An empty configured secret rejects every request (endpoint disabled)."""
    with pytest.raises(InternalSecretError, match="endpoint disabled"):
        verify_internal_secret(presented="anything", configured="")


def test_mismatch_raises() -> None:
    with pytest.raises(InternalSecretError, match="mismatch"):
        verify_internal_secret(presented="wrong", configured="s3cret")
