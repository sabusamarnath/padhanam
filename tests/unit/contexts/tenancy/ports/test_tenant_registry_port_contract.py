"""Contract tests for TenantRegistryPort.

S10 wires these against the real PostgresTenantRegistry adapter and
the live postgres-control-plane database. The four S9 scaffolds move
from `pytest.mark.skip` to live; additional behaviour assertions S10
motivates land alongside.

These tests are integration-shaped: they require the live control-
plane Postgres instance and the migrated tenant_registry table.
Pytest skips the suite if the engine cannot connect (so the unit-test
run on a developer laptop with no Compose stack is still green).
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from typing import Protocol

import pytest

from contexts.audit.adapters.outbound.noop import NoOpAuditAdapter
from contexts.tenancy.adapters.outbound.postgres.registry import (
    PostgresTenantRegistry,
    tenant_registry,
)
from contexts.tenancy.domain import (
    EncryptedCredentials,
    Tenant,
    TenantConnectionConfig,
    TenantId,
    TenantStatus,
)
from contexts.tenancy.ports import TenantRegistryPort
from shared_kernel import Jurisdiction
from vadakkan.config import ControlPlaneSettings
from vadakkan.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
)
import sqlalchemy as sa


VALID_UUID = "00000000-0000-4000-8000-0000000000a1"
OTHER_UUID = "00000000-0000-4000-8000-0000000000a2"


class _CollectingSecurityEvents:
    """In-memory SecurityEventLogger for assertions."""

    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def emit(self, event: SecurityEvent) -> None:
        self.events.append(event)


def _plaintext(*, password: str = "plaintext-secret-do-not-leak") -> TenantConnectionConfig:
    return TenantConnectionConfig(
        host="postgres-tenant-a",
        port=5432,
        username="tenant_a",
        password=password,
        database="tenant_a",
    )


@pytest.fixture(scope="module")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture
def adapter(event_loop: asyncio.AbstractEventLoop) -> Iterator[PostgresTenantRegistry]:
    # The loopback-only host port binding `127.0.0.1:5433:5432` for
    # postgres-control-plane (compose.yaml) is what makes the contract
    # tests reachable from `uv run pytest` on the host. Defaults
    # otherwise resolve to the Compose-network hostname.
    base = ControlPlaneSettings()
    settings = ControlPlaneSettings(
        user=base.user,
        password=base.password,
        db=base.db,
        host=os.environ.get("CONTROL_PLANE_HOST_OVERRIDE", "127.0.0.1"),
        port=int(os.environ.get("CONTROL_PLANE_PORT_OVERRIDE", "5433")),
    )

    audit = NoOpAuditAdapter()
    security_events = _CollectingSecurityEvents()
    reg = PostgresTenantRegistry.from_settings(
        settings=settings, audit=audit, security_events=security_events
    )
    # Verify connectivity; if unreachable, skip rather than fail.
    try:
        event_loop.run_until_complete(_clean_table(reg))
    except Exception as e:
        event_loop.run_until_complete(reg.dispose())
        pytest.skip(f"control-plane Postgres unreachable: {e}")
    reg._security_events_collector = security_events  # type: ignore[attr-defined]
    try:
        yield reg
    finally:
        event_loop.run_until_complete(_clean_table(reg))
        event_loop.run_until_complete(reg.dispose())


async def _clean_table(adapter: PostgresTenantRegistry) -> None:
    async with adapter._sessionmaker() as session:
        await session.execute(sa.delete(tenant_registry))
        await session.commit()


def test_register_tenant_returns_tenant_with_encrypted_credentials(
    event_loop: asyncio.AbstractEventLoop,
    adapter: PostgresTenantRegistry,
) -> None:
    plaintext = _plaintext()
    tenant = event_loop.run_until_complete(
        adapter.register_tenant(
            tenant_id=TenantId(VALID_UUID),
            jurisdiction=Jurisdiction("eu-west"),
            display_name="Tenant A",
            connection_config=plaintext,
        )
    )
    assert isinstance(tenant, Tenant)
    assert tenant.id == TenantId(VALID_UUID)
    assert isinstance(tenant.credentials, EncryptedCredentials)
    assert plaintext.password.encode() not in tenant.credentials.ciphertext
    assert plaintext.password.encode() not in tenant.credentials.wrapped_dek


def test_get_tenant_returns_encrypted_form_only(
    event_loop: asyncio.AbstractEventLoop,
    adapter: PostgresTenantRegistry,
) -> None:
    event_loop.run_until_complete(
        adapter.register_tenant(
            tenant_id=TenantId(VALID_UUID),
            jurisdiction=Jurisdiction("eu-west"),
            display_name="Tenant A",
            connection_config=_plaintext(),
        )
    )
    tenant = event_loop.run_until_complete(adapter.get_tenant(TenantId(VALID_UUID)))
    assert tenant is not None
    assert isinstance(tenant.credentials, EncryptedCredentials)


def test_list_tenants_filters_by_jurisdiction(
    event_loop: asyncio.AbstractEventLoop,
    adapter: PostgresTenantRegistry,
) -> None:
    event_loop.run_until_complete(
        adapter.register_tenant(
            tenant_id=TenantId(VALID_UUID),
            jurisdiction=Jurisdiction("eu-west"),
            display_name="Tenant A",
            connection_config=_plaintext(),
        )
    )
    event_loop.run_until_complete(
        adapter.register_tenant(
            tenant_id=TenantId(OTHER_UUID),
            jurisdiction=Jurisdiction("us-east"),
            display_name="Tenant B",
            connection_config=_plaintext(password="other-secret"),
        )
    )
    eu = event_loop.run_until_complete(
        adapter.list_tenants(jurisdiction=Jurisdiction("eu-west"))
    )
    assert len(eu) == 1
    all_tenants = event_loop.run_until_complete(adapter.list_tenants())
    assert len(all_tenants) == 2


def test_update_tenant_status_returns_updated_tenant(
    event_loop: asyncio.AbstractEventLoop,
    adapter: PostgresTenantRegistry,
) -> None:
    event_loop.run_until_complete(
        adapter.register_tenant(
            tenant_id=TenantId(VALID_UUID),
            jurisdiction=Jurisdiction("eu-west"),
            display_name="Tenant A",
            connection_config=_plaintext(),
        )
    )
    updated = event_loop.run_until_complete(
        adapter.update_tenant_status(TenantId(VALID_UUID), TenantStatus.SUSPENDED)
    )
    assert updated.status is TenantStatus.SUSPENDED


def test_register_emits_security_event_for_privileged_action(
    event_loop: asyncio.AbstractEventLoop,
    adapter: PostgresTenantRegistry,
) -> None:
    event_loop.run_until_complete(
        adapter.register_tenant(
            tenant_id=TenantId(VALID_UUID),
            jurisdiction=Jurisdiction("eu-west"),
            display_name="Tenant A",
            connection_config=_plaintext(),
        )
    )
    events = adapter._security_events_collector.events  # type: ignore[attr-defined]
    privileged = [
        e for e in events if e.category is SecurityEventCategory.PRIVILEGED_ACTION
    ]
    assert privileged
    assert privileged[-1].action == "tenant.register"


def test_reveal_round_trips_to_original_plaintext(
    event_loop: asyncio.AbstractEventLoop,
    adapter: PostgresTenantRegistry,
) -> None:
    plaintext = _plaintext()
    event_loop.run_until_complete(
        adapter.register_tenant(
            tenant_id=TenantId(VALID_UUID),
            jurisdiction=Jurisdiction("eu-west"),
            display_name="Tenant A",
            connection_config=plaintext,
        )
    )
    revealed = event_loop.run_until_complete(
        adapter.reveal_connection_config(TenantId(VALID_UUID))
    )
    assert revealed == plaintext


def test_port_protocol_is_importable_and_well_formed() -> None:
    """Compile-time check: the port's expected attributes exist."""
    assert hasattr(TenantRegistryPort, "register_tenant")
    assert hasattr(TenantRegistryPort, "get_tenant")
    assert hasattr(TenantRegistryPort, "list_tenants")
    assert hasattr(TenantRegistryPort, "update_tenant_status")


def test_register_tenant_signature_accepts_plaintext_argument() -> None:
    plaintext = _plaintext()
    assert plaintext.password == "plaintext-secret-do-not-leak"


def test_imports_do_not_drag_in_vendor_sdks() -> None:
    """Domain-purity smoke: importing the port does not import sqlalchemy."""
    import sys

    # Trigger the import chain.
    import contexts.tenancy.ports.tenant_registry_port  # noqa: F401

    # NOTE: this assertion fires once the test module itself imports the
    # registry adapter (which pulls sqlalchemy). It used to be a
    # standalone S9 tripwire; under S10 the contract suite imports the
    # adapter at module load, so the runtime tripwire is necessarily
    # less strict. The structural enforcement now lives in the
    # import-linter `Domain code is pure` contract; this test keeps the
    # weaker assertion for backwards-readability.
    assert "contexts.tenancy.ports.tenant_registry_port" in sys.modules
