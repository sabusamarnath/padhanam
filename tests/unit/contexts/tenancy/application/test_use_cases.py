"""Tests for tenancy use cases (D34 policy boundary)."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest

from contexts.tenancy.application import (
    OPERATOR_ROLE,
    get_tenant,
    is_operator,
    list_tenants,
    register_tenant,
    reveal_connection_config,
    update_tenant_status,
)
from contexts.tenancy.domain import (
    EncryptedCredentials,
    Tenant,
    TenantConnectionConfig,
    TenantId,
    TenantStatus,
)
from shared_kernel import Jurisdiction, TenantId as SharedTenantId
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
)
from padhanam.security import AuthorizationError, Principal


VALID_UUID = "00000000-0000-4000-8000-0000000000a1"


def _operator() -> Principal:
    return Principal(
        subject="system:control_plane",
        tenant_id=SharedTenantId("operator"),
        roles=frozenset({OPERATOR_ROLE}),
        credential_ref="dev-token-op...",
    )


def _tenant_caller() -> Principal:
    return Principal(
        subject="alice",
        tenant_id=SharedTenantId(VALID_UUID),
        roles=frozenset({"audit.read"}),
        credential_ref="dev-token-a...",
    )


class _FakeRegistry:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.plaintext = TenantConnectionConfig(
            host="postgres-tenant-a",
            port=5432,
            username="tenant_a",
            password="hunter2",
            database="tenant_a",
        )
        self.tenant = Tenant(
            id=TenantId(VALID_UUID),
            jurisdiction=Jurisdiction("eu-west"),
            display_name="Tenant A",
            credentials=EncryptedCredentials(
                wrapped_dek=b"\x01\x02",
                ciphertext=b"\x03\x04",
                aad=b"\x05",
            ),
            status=TenantStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
        )

    async def register_tenant(self, **kwargs):
        self.calls.append(("register_tenant", kwargs))
        return self.tenant

    async def get_tenant(self, tenant_id):
        self.calls.append(("get_tenant", tenant_id))
        return self.tenant

    async def list_tenants(self, jurisdiction=None):
        self.calls.append(("list_tenants", jurisdiction))
        return [self.tenant]

    async def update_tenant_status(self, tenant_id, status):
        self.calls.append(("update_tenant_status", tenant_id, status))
        return self.tenant

    async def reveal_connection_config(self, tenant_id):
        self.calls.append(("reveal_connection_config", tenant_id))
        return self.plaintext


class _CollectingSecurityEvents:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def emit(self, event: SecurityEvent) -> None:
        self.events.append(event)


@pytest.fixture
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


def test_is_operator_predicate_recognises_operator_role() -> None:
    assert is_operator(_operator()) is True


def test_is_operator_predicate_rejects_tenant_caller() -> None:
    assert is_operator(_tenant_caller()) is False


def test_register_tenant_rejects_tenant_caller(event_loop) -> None:
    registry = _FakeRegistry()
    sec = _CollectingSecurityEvents()
    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            register_tenant(
                principal=_tenant_caller(),
                registry=registry,
                security_events=sec,
                tenant_id=TenantId(VALID_UUID),
                jurisdiction=Jurisdiction("eu-west"),
                display_name="Tenant A",
                connection_config=registry.plaintext,
            )
        )
    assert any(
        e.category is SecurityEventCategory.AUTHZ_DENIAL for e in sec.events
    )
    assert registry.calls == []


def test_register_tenant_allows_operator(event_loop) -> None:
    registry = _FakeRegistry()
    sec = _CollectingSecurityEvents()
    tenant = event_loop.run_until_complete(
        register_tenant(
            principal=_operator(),
            registry=registry,
            security_events=sec,
            tenant_id=TenantId(VALID_UUID),
            jurisdiction=Jurisdiction("eu-west"),
            display_name="Tenant A",
            connection_config=registry.plaintext,
        )
    )
    assert tenant is registry.tenant
    assert registry.calls[0][0] == "register_tenant"


def test_reveal_rejects_tenant_caller_even_for_own_tenant(event_loop) -> None:
    """Critical D34 invariant: tenant-context cannot reveal own credentials."""
    registry = _FakeRegistry()
    sec = _CollectingSecurityEvents()
    own_tenant_caller = Principal(
        subject="alice",
        tenant_id=SharedTenantId(VALID_UUID),
        roles=frozenset({"audit.read"}),
        credential_ref="dev-token-a...",
    )
    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            reveal_connection_config(
                principal=own_tenant_caller,
                registry=registry,
                security_events=sec,
                tenant_id=TenantId(VALID_UUID),
            )
        )
    assert any(
        e.category is SecurityEventCategory.AUTHZ_DENIAL
        and e.action == "tenant.reveal_credentials"
        for e in sec.events
    )
    assert registry.calls == []


def test_reveal_allows_operator_and_returns_plaintext(event_loop) -> None:
    registry = _FakeRegistry()
    sec = _CollectingSecurityEvents()
    plaintext = event_loop.run_until_complete(
        reveal_connection_config(
            principal=_operator(),
            registry=registry,
            security_events=sec,
            tenant_id=TenantId(VALID_UUID),
        )
    )
    assert plaintext is registry.plaintext
    assert any(
        e.category is SecurityEventCategory.PRIVILEGED_ACTION
        and e.action == "tenant.reveal_credentials"
        for e in sec.events
    )


def test_update_status_rejects_tenant_caller(event_loop) -> None:
    registry = _FakeRegistry()
    sec = _CollectingSecurityEvents()
    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            update_tenant_status(
                principal=_tenant_caller(),
                registry=registry,
                security_events=sec,
                tenant_id=TenantId(VALID_UUID),
                status=TenantStatus.SUSPENDED,
            )
        )
    assert registry.calls == []


def test_get_tenant_allows_any_authenticated_caller(event_loop) -> None:
    registry = _FakeRegistry()
    sec = _CollectingSecurityEvents()
    tenant = event_loop.run_until_complete(
        get_tenant(
            principal=_tenant_caller(),
            registry=registry,
            security_events=sec,
            tenant_id=TenantId(VALID_UUID),
        )
    )
    assert tenant is registry.tenant


def test_list_tenants_allows_any_authenticated_caller(event_loop) -> None:
    registry = _FakeRegistry()
    sec = _CollectingSecurityEvents()
    tenants = event_loop.run_until_complete(
        list_tenants(
            principal=_tenant_caller(),
            registry=registry,
            security_events=sec,
            jurisdiction=Jurisdiction("eu-west"),
        )
    )
    assert tenants == [registry.tenant]
