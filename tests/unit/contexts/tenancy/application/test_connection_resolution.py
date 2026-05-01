"""Tests for the per-tenant connection resolution layer (D36)."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from contexts.tenancy.application import (
    OPERATOR_ROLE,
    TenantSessionFactoryCache,
    update_tenant_status,
)
from contexts.tenancy.domain import (
    TenantConnectionConfig,
    TenantId,
    TenantStatus,
)
from shared_kernel import TenantId as SharedTenantId
from padhanam.observability.security_events import SecurityEvent
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
    """Registry stub that returns plaintext on reveal."""

    def __init__(self) -> None:
        self.reveal_calls: int = 0
        self.update_calls: list[tuple] = []
        self.plaintext = TenantConnectionConfig(
            host="postgres-tenant-a",
            port=5432,
            username="tenant_a",
            password="hunter2",
            database="tenant_a",
        )

    async def reveal_connection_config(self, tenant_id):
        self.reveal_calls += 1
        return self.plaintext

    async def update_tenant_status(self, tenant_id, status):
        self.update_calls.append((tenant_id, status))
        # Returning a placeholder; the use case forwards whatever the
        # registry returns, and the cache-invalidation behaviour does
        # not depend on the Tenant value.
        return ("tenant", tenant_id, status)


class _FakeEngine:
    def __init__(self) -> None:
        self.disposed: bool = False

    async def dispose(self) -> None:
        self.disposed = True


class _FakeSessionmaker:
    """Stand-in for async_sessionmaker. Identity is what matters in tests."""

    def __init__(self, engine: _FakeEngine) -> None:
        self.engine = engine


class _FakeFactory:
    """Records construction calls; returns a fresh (engine, sessionmaker)."""

    def __init__(self) -> None:
        self.calls: list[TenantConnectionConfig] = []

    def create_engine_and_sessionmaker(self, plaintext):
        self.calls.append(plaintext)
        engine = _FakeEngine()
        sessionmaker = _FakeSessionmaker(engine)
        return engine, sessionmaker


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


def test_cache_miss_constructs_factory(event_loop) -> None:
    factory = _FakeFactory()
    cache = TenantSessionFactoryCache(factory)
    registry = _FakeRegistry()
    sec = _CollectingSecurityEvents()

    sessionmaker = event_loop.run_until_complete(
        cache.get(
            tenant_id=TenantId(VALID_UUID),
            principal=_operator(),
            registry=registry,
            security_events=sec,
        )
    )
    assert isinstance(sessionmaker, _FakeSessionmaker)
    assert factory.calls == [registry.plaintext]
    assert registry.reveal_calls == 1


def test_cache_hit_returns_same_instance(event_loop) -> None:
    factory = _FakeFactory()
    cache = TenantSessionFactoryCache(factory)
    registry = _FakeRegistry()
    sec = _CollectingSecurityEvents()

    first = event_loop.run_until_complete(
        cache.get(
            tenant_id=TenantId(VALID_UUID),
            principal=_operator(),
            registry=registry,
            security_events=sec,
        )
    )
    second = event_loop.run_until_complete(
        cache.get(
            tenant_id=TenantId(VALID_UUID),
            principal=_operator(),
            registry=registry,
            security_events=sec,
        )
    )
    assert first is second
    assert registry.reveal_calls == 1
    assert len(factory.calls) == 1


def test_tenant_context_caller_is_rejected(event_loop) -> None:
    factory = _FakeFactory()
    cache = TenantSessionFactoryCache(factory)
    registry = _FakeRegistry()
    sec = _CollectingSecurityEvents()

    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            cache.get(
                tenant_id=TenantId(VALID_UUID),
                principal=_tenant_caller(),
                registry=registry,
                security_events=sec,
            )
        )
    assert factory.calls == []
    assert registry.reveal_calls == 0


def test_invalidate_disposes_engine_and_removes_entry(event_loop) -> None:
    factory = _FakeFactory()
    cache = TenantSessionFactoryCache(factory)
    registry = _FakeRegistry()
    sec = _CollectingSecurityEvents()
    tenant_id = TenantId(VALID_UUID)

    sessionmaker = event_loop.run_until_complete(
        cache.get(
            tenant_id=tenant_id,
            principal=_operator(),
            registry=registry,
            security_events=sec,
        )
    )
    engine = sessionmaker.engine

    event_loop.run_until_complete(cache.invalidate(tenant_id))
    assert engine.disposed is True

    # Subsequent get() reconstructs.
    second = event_loop.run_until_complete(
        cache.get(
            tenant_id=tenant_id,
            principal=_operator(),
            registry=registry,
            security_events=sec,
        )
    )
    assert second is not sessionmaker
    assert registry.reveal_calls == 2
    assert len(factory.calls) == 2


def test_invalidate_unknown_tenant_is_a_no_op(event_loop) -> None:
    factory = _FakeFactory()
    cache = TenantSessionFactoryCache(factory)
    event_loop.run_until_complete(cache.invalidate(TenantId(VALID_UUID)))


def test_dispose_all_disposes_every_engine(event_loop) -> None:
    factory = _FakeFactory()
    cache = TenantSessionFactoryCache(factory)
    registry = _FakeRegistry()
    sec = _CollectingSecurityEvents()
    tenant_a = TenantId(VALID_UUID)
    tenant_b = TenantId("00000000-0000-4000-8000-0000000000b2")

    sm_a = event_loop.run_until_complete(
        cache.get(
            tenant_id=tenant_a,
            principal=_operator(),
            registry=registry,
            security_events=sec,
        )
    )
    sm_b = event_loop.run_until_complete(
        cache.get(
            tenant_id=tenant_b,
            principal=_operator(),
            registry=registry,
            security_events=sec,
        )
    )
    event_loop.run_until_complete(cache.dispose_all())
    assert sm_a.engine.disposed is True
    assert sm_b.engine.disposed is True


def test_update_status_invalidates_cache(event_loop) -> None:
    """Status transition flushes the per-tenant cached factory (D36)."""
    factory = _FakeFactory()
    cache = TenantSessionFactoryCache(factory)
    registry = _FakeRegistry()
    sec = _CollectingSecurityEvents()
    tenant_id = TenantId(VALID_UUID)

    sessionmaker = event_loop.run_until_complete(
        cache.get(
            tenant_id=tenant_id,
            principal=_operator(),
            registry=registry,
            security_events=sec,
        )
    )
    engine_before = sessionmaker.engine

    event_loop.run_until_complete(
        update_tenant_status(
            principal=_operator(),
            registry=registry,
            security_events=sec,
            tenant_id=tenant_id,
            status=TenantStatus.SUSPENDED,
            session_factory_cache=cache,
        )
    )
    assert engine_before.disposed is True
    assert registry.update_calls == [(tenant_id, TenantStatus.SUSPENDED)]

    # Next get() rebuilds from the registry.
    after = event_loop.run_until_complete(
        cache.get(
            tenant_id=tenant_id,
            principal=_operator(),
            registry=registry,
            security_events=sec,
        )
    )
    assert after is not sessionmaker
    assert registry.reveal_calls == 2
