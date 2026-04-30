from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from contexts.tenancy.domain import TenantConnectionConfig


def test_constructs_with_required_fields() -> None:
    cfg = TenantConnectionConfig(
        host="postgres-tenant-a",
        port=5432,
        username="tenant_a",
        password="tenant_a",
        database="tenant_a",
    )
    assert cfg.host == "postgres-tenant-a"
    assert cfg.port == 5432
    assert cfg.username == "tenant_a"
    assert cfg.database == "tenant_a"


def test_is_immutable() -> None:
    cfg = TenantConnectionConfig(
        host="h", port=1, username="u", password="p", database="d"
    )
    with pytest.raises(FrozenInstanceError):
        cfg.password = "q"  # type: ignore[misc]


def test_equality_by_field_values() -> None:
    a = TenantConnectionConfig(
        host="h", port=1, username="u", password="p", database="d"
    )
    b = TenantConnectionConfig(
        host="h", port=1, username="u", password="p", database="d"
    )
    other = TenantConnectionConfig(
        host="h", port=2, username="u", password="p", database="d"
    )
    assert a == b
    assert a != other
