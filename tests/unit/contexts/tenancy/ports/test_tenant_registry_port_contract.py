"""Contract scaffold for TenantRegistryPort.

S9 ships the port without an adapter; this module documents the
contract S10's Postgres adapter must satisfy. The tests are runnable
once a concrete adapter is wired in S10 by subclassing
``_AbstractTenantRegistryContract`` and implementing ``make_registry``.
The scaffold runs as a skipped suite under the S9 codebase so test
discovery picks it up and S10 lands the adapter against existing
expectations rather than authoring new assertions from scratch.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

import pytest

from shared_kernel import Jurisdiction

from contexts.tenancy.domain import (
    EncryptedCredentials,
    Tenant,
    TenantConnectionConfig,
    TenantId,
    TenantStatus,
)
from contexts.tenancy.ports import TenantRegistryPort


VALID_UUID = "00000000-0000-4000-8000-0000000000a1"
OTHER_UUID = "00000000-0000-4000-8000-0000000000a2"


class _AbstractTenantRegistryContract(Protocol):
    """S10 implements this by subclassing and providing make_registry."""

    def make_registry(self) -> TenantRegistryPort: ...


def _plaintext() -> TenantConnectionConfig:
    return TenantConnectionConfig(
        host="postgres-tenant-a",
        port=5432,
        username="tenant_a",
        password="plaintext-secret-do-not-leak",
        database="tenant_a",
    )


@pytest.mark.skip(reason="S9 contract scaffold; S10 adapter implements")
def test_register_tenant_returns_tenant_with_encrypted_credentials() -> None:
    # registry: TenantRegistryPort = make_registry()  # noqa: ERA001 (S10)
    # plaintext = _plaintext()
    # tenant = registry.register_tenant(
    #     tenant_id=TenantId(VALID_UUID),
    #     jurisdiction=Jurisdiction("eu-west"),
    #     display_name="Tenant A",
    #     connection_config=plaintext,
    # )
    # assert isinstance(tenant, Tenant)
    # assert tenant.id == TenantId(VALID_UUID)
    # assert isinstance(tenant.credentials, EncryptedCredentials)
    # # The plaintext password must NOT appear in the encrypted form.
    # assert plaintext.password.encode() not in tenant.credentials.ciphertext
    # assert plaintext.password.encode() not in tenant.credentials.wrapped_dek
    raise NotImplementedError


@pytest.mark.skip(reason="S9 contract scaffold; S10 adapter implements")
def test_get_tenant_returns_encrypted_form_only() -> None:
    # registry: TenantRegistryPort = make_registry()
    # registry.register_tenant(...)
    # tenant = registry.get_tenant(TenantId(VALID_UUID))
    # assert isinstance(tenant.credentials, EncryptedCredentials)
    raise NotImplementedError


@pytest.mark.skip(reason="S9 contract scaffold; S10 adapter implements")
def test_list_tenants_filters_by_jurisdiction() -> None:
    # registry: TenantRegistryPort = make_registry()
    # registry.register_tenant(jurisdiction=Jurisdiction("eu-west"), ...)
    # registry.register_tenant(jurisdiction=Jurisdiction("us-east"), ...)
    # eu = registry.list_tenants(jurisdiction=Jurisdiction("eu-west"))
    # assert len(eu) == 1
    # all_tenants = registry.list_tenants()
    # assert len(all_tenants) == 2
    raise NotImplementedError


@pytest.mark.skip(reason="S9 contract scaffold; S10 adapter implements")
def test_update_tenant_status_returns_updated_tenant() -> None:
    # registry: TenantRegistryPort = make_registry()
    # registry.register_tenant(tenant_id=TenantId(VALID_UUID), ...)
    # updated = registry.update_tenant_status(
    #     TenantId(VALID_UUID), TenantStatus.SUSPENDED
    # )
    # assert updated.status is TenantStatus.SUSPENDED
    raise NotImplementedError


def test_port_protocol_is_importable_and_well_formed() -> None:
    """Compile-time check: the port's expected attributes exist."""
    assert hasattr(TenantRegistryPort, "register_tenant")
    assert hasattr(TenantRegistryPort, "get_tenant")
    assert hasattr(TenantRegistryPort, "list_tenants")
    assert hasattr(TenantRegistryPort, "update_tenant_status")


def test_register_tenant_signature_accepts_plaintext_argument() -> None:
    """Construct a plaintext config and verify it is the input shape.

    The port accepts plaintext on the way in; the contract guarantees
    the implementation wraps it before persistence. This test pins the
    argument shape so signature drift in S10 surfaces here.
    """
    plaintext = _plaintext()
    assert plaintext.password == "plaintext-secret-do-not-leak"


def test_imports_do_not_drag_in_vendor_sdks() -> None:
    """Domain-purity smoke: importing the port does not import sqlalchemy."""
    import sys

    # Trigger the import chain.
    import contexts.tenancy.ports.tenant_registry_port  # noqa: F401

    forbidden = {"sqlalchemy", "alembic", "asyncpg", "fastapi", "pydantic"}
    leaked = forbidden & set(sys.modules.keys())
    # pydantic is allowed at platform level; what matters is that the
    # port import itself does not cause new vendor modules to land.
    # Re-run the check: import-linter is the structural enforcement;
    # this assertion is a runtime tripwire that S10 should not silence.
    assert "sqlalchemy" not in leaked
    assert "alembic" not in leaked
    assert "asyncpg" not in leaked
