"""Per-tenant connection resolution use case (D36).

Composes ``reveal_connection_config`` (operator-context system actor)
with the SQLAlchemy session factory adapter, caching the resulting
``async_sessionmaker`` per ``TenantId`` so the KEK-unwrap path stays
off the request hot path.

Cache lifecycle
---------------
The cache is process-local. Cache miss → call
``reveal_connection_config`` (which enforces operator-context policy
and emits a privileged-action security event) → construct engine via
the factory adapter → store and return. Cache hit → return the cached
sessionmaker.

The plaintext ``TenantConnectionConfig`` lives only in the function-
local scope between ``reveal_connection_config`` returning and the
engine being constructed; it is never assigned to module state, never
cached, never logged. The cache stores ``(AsyncEngine,
async_sessionmaker)`` pairs only.

Invalidation
------------
``invalidate_tenant_session_factory(tenant_id)`` disposes the cached
engine via ``await engine.dispose()`` and removes the entry. The
``update_tenant_status`` use case calls invalidation after the registry
update succeeds so any status transition (suspend, deprovision,
reactivate) flushes the cache. Other registry mutation paths
(credential rotation, jurisdiction change, instance re-pointing) are
not yet wired in S11; when they land, they must call invalidation
similarly — this is the only mutation path that needs the hook.

In production multi-replica deployments, each replica maintains its
own cache; cross-replica invalidation propagates via registry-update
events on the domain bus (deferred to event-bus integration). Single-
replica dev makes this a non-issue at S11.
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from contexts.tenancy.application.use_cases import reveal_connection_config
from contexts.tenancy.domain.tenant_connection_config import TenantConnectionConfig
from contexts.tenancy.domain.tenant_id import TenantId
from vadakkan.observability.security_events import SecurityEventLogger
from vadakkan.security import Principal


class _SessionFactoryAdapter(Protocol):
    """Shape of the SQLAlchemy session factory adapter."""

    def create_engine_and_sessionmaker(
        self, plaintext: TenantConnectionConfig
    ) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]: ...


class _AsyncRegistryPort(Protocol):
    async def reveal_connection_config(
        self, tenant_id: TenantId
    ) -> TenantConnectionConfig: ...


class TenantSessionFactoryCache:
    """Process-local cache of per-tenant session factories (D36).

    Holds ``(engine, sessionmaker)`` pairs keyed by ``TenantId``. The
    AST enforcement test asserts no field is typed as
    ``TenantConnectionConfig``; only encrypted-or-derived state lives
    in instance attributes here.
    """

    def __init__(self, factory: _SessionFactoryAdapter) -> None:
        self._factory = factory
        self._engines: dict[TenantId, AsyncEngine] = {}
        self._sessionmakers: dict[TenantId, async_sessionmaker[AsyncSession]] = {}

    async def get(
        self,
        *,
        tenant_id: TenantId,
        principal: Principal,
        registry: _AsyncRegistryPort,
        security_events: SecurityEventLogger,
    ) -> async_sessionmaker[AsyncSession]:
        cached = self._sessionmakers.get(tenant_id)
        if cached is not None:
            return cached
        plaintext = await reveal_connection_config(
            principal=principal,
            registry=registry,
            security_events=security_events,
            tenant_id=tenant_id,
        )
        engine, sessionmaker = self._factory.create_engine_and_sessionmaker(plaintext)
        self._engines[tenant_id] = engine
        self._sessionmakers[tenant_id] = sessionmaker
        return sessionmaker

    async def invalidate(self, tenant_id: TenantId) -> None:
        engine = self._engines.pop(tenant_id, None)
        self._sessionmakers.pop(tenant_id, None)
        if engine is not None:
            await engine.dispose()

    async def dispose_all(self) -> None:
        engines = list(self._engines.values())
        self._engines.clear()
        self._sessionmakers.clear()
        for engine in engines:
            await engine.dispose()
