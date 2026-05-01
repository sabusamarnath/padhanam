"""Shared fixtures for tenant isolation contract tests.

Two principals, one per tenant. Tests assert that operations performed as
principal A cannot read or affect tenant B's resources, and vice versa.
"""

from __future__ import annotations

import pytest

from padhanam.security.auth import Principal
from shared_kernel import TenantId


@pytest.fixture
def tenant_a_principal() -> Principal:
    return Principal(
        subject="alice",
        tenant_id=TenantId("tenant-a"),
        roles=frozenset({"audit.read", "audit.write"}),
        credential_ref="dev-token-a...",
    )


@pytest.fixture
def tenant_b_principal() -> Principal:
    return Principal(
        subject="bob",
        tenant_id=TenantId("tenant-b"),
        roles=frozenset({"audit.read", "audit.write"}),
        credential_ref="dev-token-b...",
    )
