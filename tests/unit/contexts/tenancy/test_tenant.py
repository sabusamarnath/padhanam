from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from shared_kernel import Jurisdiction

from contexts.tenancy.domain import (
    EncryptedCredentials,
    Tenant,
    TenantId,
    TenantStatus,
)


VALID_UUID = "00000000-0000-4000-8000-0000000000aa"


def _build_tenant() -> Tenant:
    return Tenant(
        id=TenantId(VALID_UUID),
        jurisdiction=Jurisdiction("eu-west"),
        display_name="Tenant A",
        credentials=EncryptedCredentials(
            wrapped_dek=b"\x01", ciphertext=b"\x02", aad=b"\x03"
        ),
        status=TenantStatus.ACTIVE,
        created_at=datetime(2026, 4, 30, tzinfo=timezone.utc),
    )


def test_aggregate_composes_value_objects() -> None:
    t = _build_tenant()
    assert t.id == TenantId(VALID_UUID)
    assert t.jurisdiction == Jurisdiction("eu-west")
    assert t.display_name == "Tenant A"
    assert t.credentials.wrapped_dek == b"\x01"
    assert t.status is TenantStatus.ACTIVE
    assert t.created_at.year == 2026


def test_aggregate_is_immutable() -> None:
    t = _build_tenant()
    with pytest.raises(FrozenInstanceError):
        t.display_name = "Other"  # type: ignore[misc]


def test_status_values() -> None:
    assert {s.value for s in TenantStatus} == {
        "active",
        "suspended",
        "deprovisioned",
    }
