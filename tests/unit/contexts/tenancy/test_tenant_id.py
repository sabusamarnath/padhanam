from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from contexts.tenancy.domain import TenantId


VALID_UUID = "00000000-0000-4000-8000-000000000001"


def test_accepts_valid_uuid_string() -> None:
    tid = TenantId(VALID_UUID)
    assert tid.value == VALID_UUID
    assert str(tid) == VALID_UUID


def test_rejects_non_uuid_string() -> None:
    with pytest.raises(ValueError, match="must be a UUID"):
        TenantId("tenant-a")


def test_rejects_empty_string() -> None:
    with pytest.raises(ValueError):
        TenantId("")


def test_is_immutable() -> None:
    tid = TenantId(VALID_UUID)
    with pytest.raises(FrozenInstanceError):
        tid.value = "other"  # type: ignore[misc]


def test_equality_by_value() -> None:
    a = TenantId(VALID_UUID)
    b = TenantId(VALID_UUID)
    other = TenantId("00000000-0000-4000-8000-000000000002")
    assert a == b
    assert a != other
    assert hash(a) == hash(b)
