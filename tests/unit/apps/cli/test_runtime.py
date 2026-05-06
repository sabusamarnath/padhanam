"""Unit tests for the CLI runtime composition helpers (S18)."""

from __future__ import annotations

import pytest

from apps.cli._runtime import resolve_tenant_context


def test_resolve_tenant_context_accepts_short_label_a() -> None:
    ctx, label = resolve_tenant_context("a")
    assert label == "a"
    assert ctx.tenant_id == "00000000-0000-4000-8000-00000000a001"
    assert ctx.jurisdiction == "eu-west"
    assert ctx.cost_attribution_id == ctx.tenant_id


def test_resolve_tenant_context_accepts_short_label_b() -> None:
    ctx, label = resolve_tenant_context("b")
    assert label == "b"
    assert ctx.tenant_id == "00000000-0000-4000-8000-00000000b002"


def test_resolve_tenant_context_accepts_uuid_in_test_set() -> None:
    ctx, label = resolve_tenant_context(
        "00000000-0000-4000-8000-00000000a001"
    )
    assert label == "a"
    assert ctx.tenant_id == "00000000-0000-4000-8000-00000000a001"


def test_resolve_tenant_context_rejects_unknown_tenant() -> None:
    with pytest.raises(ValueError, match="unknown --tenant-id"):
        resolve_tenant_context("c")


def test_resolve_tenant_context_rejects_non_test_set_uuid() -> None:
    with pytest.raises(ValueError, match="unknown --tenant-id"):
        resolve_tenant_context("00000000-0000-4000-8000-00000000c003")
