"""Unit tests for the TenantContext value object."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from shared_kernel import TenantContext


def _ok() -> TenantContext:
    return TenantContext(
        tenant_id="00000000-0000-4000-8000-00000000a001",
        jurisdiction="eu-west",
        cost_attribution_id="00000000-0000-4000-8000-00000000a001",
    )


def test_construction_happy_path() -> None:
    ctx = _ok()
    assert ctx.tenant_id == "00000000-0000-4000-8000-00000000a001"
    assert ctx.jurisdiction == "eu-west"
    assert ctx.cost_attribution_id == "00000000-0000-4000-8000-00000000a001"


def test_immutable_attributes() -> None:
    ctx = _ok()
    with pytest.raises(FrozenInstanceError):
        ctx.tenant_id = "other"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        ctx.jurisdiction = "other"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        ctx.cost_attribution_id = "other"  # type: ignore[misc]


def test_empty_tenant_id_rejected() -> None:
    with pytest.raises(ValueError, match="tenant_id"):
        TenantContext(
            tenant_id="",
            jurisdiction="eu-west",
            cost_attribution_id="abc",
        )


def test_empty_jurisdiction_rejected() -> None:
    with pytest.raises(ValueError, match="jurisdiction"):
        TenantContext(
            tenant_id="abc",
            jurisdiction="",
            cost_attribution_id="abc",
        )


def test_empty_cost_attribution_id_rejected() -> None:
    with pytest.raises(ValueError, match="cost_attribution_id"):
        TenantContext(
            tenant_id="abc",
            jurisdiction="eu-west",
            cost_attribution_id="",
        )


def test_value_equality() -> None:
    """Frozen dataclasses use value equality — load-bearing for caches
    and cross-context comparisons."""
    a = _ok()
    b = _ok()
    assert a == b
    assert hash(a) == hash(b)
