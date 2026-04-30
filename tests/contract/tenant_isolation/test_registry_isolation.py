"""Tenant isolation tests for the registry adapter (D34 control (c)).

Five red-team-shaped scenarios verify the structural discipline, the
policy boundary, and the AAD-binding's tenant-replay protection on
the PostgresTenantRegistry adapter wired against the live control-
plane database.

Scenarios:

1. Tenant-context caller for tenant A attempts
   ``reveal_connection_config(tenant_b_id)``. Must raise
   AuthorizationError; security event emitted with
   ``category=authz_denial``.

2. Tenant-context caller for tenant A attempts
   ``reveal_connection_config(tenant_a_id)``. Must raise
   AuthorizationError (tenant-context cannot reveal own credentials
   per D34); security event emitted.

3. Tenant-context caller for tenant A queries
   ``get_tenant(tenant_b_id)``. Returns Tenant aggregate with
   EncryptedCredentials only — adapter does not scope reads on
   tenant_id at S10 (the encrypted form is safe; future routing
   contexts may add tenant-scoped read filtering).

4. Operator-context caller invokes ``reveal_connection_config(
   tenant_a_id)``. Returns the original plaintext.

5. AAD-mismatch attempt: read EncryptedCredentials for tenant A,
   construct a manual decrypt using tenant B's AAD context. Must
   raise InvalidTag from the cryptography layer — proof that AAD
   binding catches cross-tenant ciphertext replay.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator

import pytest
from cryptography.exceptions import InvalidTag

from contexts.audit.adapters.outbound.noop import NoOpAuditAdapter
from contexts.tenancy.adapters.outbound.postgres.registry import (
    CREDENTIAL_PURPOSE,
    PostgresTenantRegistry,
    tenant_registry,
)
from contexts.tenancy.application import (
    OPERATOR_ROLE,
    get_tenant,
    reveal_connection_config,
)
from contexts.tenancy.domain import (
    EncryptedCredentials,
    Tenant,
    TenantConnectionConfig,
    TenantId,
)
from shared_kernel import Jurisdiction, TenantId as SharedTenantId
from vadakkan.config import ControlPlaneSettings
from vadakkan.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
)
from vadakkan.security import AuthorizationError, Principal, crypto
import sqlalchemy as sa


TENANT_A_UUID = "00000000-0000-4000-8000-000000000a01"
TENANT_B_UUID = "00000000-0000-4000-8000-000000000b02"


def _plaintext(*, password: str = "tenant-a-secret") -> TenantConnectionConfig:
    return TenantConnectionConfig(
        host="postgres-tenant-a",
        port=5432,
        username="tenant_a",
        password=password,
        database="tenant_a",
    )


def _operator_principal() -> Principal:
    return Principal(
        subject="system:control_plane",
        tenant_id=SharedTenantId("operator"),
        roles=frozenset({OPERATOR_ROLE}),
        credential_ref="dev-token-op...",
    )


def _tenant_a_principal() -> Principal:
    return Principal(
        subject="alice",
        tenant_id=SharedTenantId(TENANT_A_UUID),
        roles=frozenset({"audit.read", "audit.write"}),
        credential_ref="dev-token-a...",
    )


class _CollectingSecurityEvents:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def emit(self, event: SecurityEvent) -> None:
        self.events.append(event)


@pytest.fixture(scope="module")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture
def registry_with_tenants(
    event_loop: asyncio.AbstractEventLoop,
) -> Iterator[tuple[PostgresTenantRegistry, _CollectingSecurityEvents]]:
    base = ControlPlaneSettings()
    settings = ControlPlaneSettings(
        user=base.user,
        password=base.password,
        db=base.db,
        host=os.environ.get("CONTROL_PLANE_HOST_OVERRIDE", "127.0.0.1"),
        port=int(os.environ.get("CONTROL_PLANE_PORT_OVERRIDE", "5433")),
    )
    audit = NoOpAuditAdapter()
    sec = _CollectingSecurityEvents()
    reg = PostgresTenantRegistry.from_settings(
        settings=settings, audit=audit, security_events=sec
    )
    try:
        async def setup() -> None:
            async with reg._sessionmaker() as session:
                await session.execute(sa.delete(tenant_registry))
                await session.commit()
            await reg.register_tenant(
                tenant_id=TenantId(TENANT_A_UUID),
                jurisdiction=Jurisdiction("eu-west"),
                display_name="Tenant A",
                connection_config=_plaintext(),
            )
            await reg.register_tenant(
                tenant_id=TenantId(TENANT_B_UUID),
                jurisdiction=Jurisdiction("us-east"),
                display_name="Tenant B",
                connection_config=_plaintext(password="tenant-b-secret"),
            )
            # Drain registration security events so test-scope
            # assertions only see events from the test action.
            sec.events.clear()
        event_loop.run_until_complete(setup())
    except Exception as e:
        event_loop.run_until_complete(reg.dispose())
        pytest.skip(f"control-plane Postgres unreachable: {e}")
    try:
        yield reg, sec
    finally:
        async def teardown() -> None:
            async with reg._sessionmaker() as session:
                await session.execute(sa.delete(tenant_registry))
                await session.commit()
            await reg.dispose()
        event_loop.run_until_complete(teardown())


def test_tenant_a_cannot_reveal_tenant_b_credentials(
    event_loop, registry_with_tenants
) -> None:
    reg, sec = registry_with_tenants
    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            reveal_connection_config(
                principal=_tenant_a_principal(),
                registry=reg,
                security_events=sec,
                tenant_id=TenantId(TENANT_B_UUID),
            )
        )
    assert any(
        e.category is SecurityEventCategory.AUTHZ_DENIAL
        and e.action == "tenant.reveal_credentials"
        for e in sec.events
    )


def test_tenant_a_cannot_reveal_own_credentials(
    event_loop, registry_with_tenants
) -> None:
    """D34 invariant: tenant-context cannot reveal even own credentials."""
    reg, sec = registry_with_tenants
    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            reveal_connection_config(
                principal=_tenant_a_principal(),
                registry=reg,
                security_events=sec,
                tenant_id=TenantId(TENANT_A_UUID),
            )
        )
    assert any(
        e.category is SecurityEventCategory.AUTHZ_DENIAL for e in sec.events
    )


def test_tenant_a_get_tenant_b_returns_encrypted_form(
    event_loop, registry_with_tenants
) -> None:
    """get_tenant returns the encrypted form to any authenticated caller.

    Adapter-level tenant-scoped read filtering is a future routing
    concern; the encrypted form is safe to expose because the
    decryption path is guarded by reveal_connection_config's policy.
    """
    reg, sec = registry_with_tenants
    tenant = event_loop.run_until_complete(
        get_tenant(
            principal=_tenant_a_principal(),
            registry=reg,
            security_events=sec,
            tenant_id=TenantId(TENANT_B_UUID),
        )
    )
    assert isinstance(tenant, Tenant)
    assert isinstance(tenant.credentials, EncryptedCredentials)
    assert b"tenant-b-secret" not in tenant.credentials.ciphertext


def test_operator_can_reveal_tenant_a_credentials(
    event_loop, registry_with_tenants
) -> None:
    reg, sec = registry_with_tenants
    plaintext = event_loop.run_until_complete(
        reveal_connection_config(
            principal=_operator_principal(),
            registry=reg,
            security_events=sec,
            tenant_id=TenantId(TENANT_A_UUID),
        )
    )
    assert isinstance(plaintext, TenantConnectionConfig)
    assert plaintext.password == "tenant-a-secret"


def test_aad_mismatch_blocks_cross_tenant_replay(
    event_loop, registry_with_tenants
) -> None:
    """Read tenant A's wire-level fields, attempt decryption against
    tenant B's AAD context. Must raise InvalidTag — proof that AAD
    binding prevents wrapped-DEK + ciphertext replay across tenants.
    """
    reg, sec = registry_with_tenants

    async def fetch_wire(uuid: str) -> crypto.EncryptedField:
        async with reg._sessionmaker() as session:
            result = await session.execute(
                sa.select(tenant_registry).where(
                    tenant_registry.c.tenant_id == uuid
                )
            )
            row = result.mappings().first()
        return crypto.EncryptedField(
            wrapped_dek=bytes(row["wrapped_dek"]),
            dek_wrap_nonce=bytes(row["dek_wrap_nonce"]),
            ciphertext=bytes(row["ciphertext"]),
            nonce=bytes(row["nonce"]),
            key_version=int(row["key_version"]),
        )

    wire_a = event_loop.run_until_complete(fetch_wire(TENANT_A_UUID))

    aad_b = {"tenant_id": TENANT_B_UUID, "purpose": CREDENTIAL_PURPOSE}
    with pytest.raises(InvalidTag):
        crypto.decrypt_field(wire_a, aad_b)
