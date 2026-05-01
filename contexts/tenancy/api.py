"""Public query interface for the tenancy context (D17, D36).

Per D17, every context exposes a single api.py at its root with read-
only query methods other contexts may call. Tenancy's read surface is
the use cases under ``contexts.tenancy.application`` re-exported here.
S11 adds the connection-resolution facade per D36 — operator-context
callers receive a per-tenant ``async_sessionmaker`` and the cache
manages engine lifecycle behind the scenes.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.tenancy.application import (
    get_tenant,
    list_tenants,
    register_tenant,
    reveal_connection_config,
    update_tenant_status,
)
from contexts.tenancy.application.connection_resolution import (
    TenantSessionFactoryCache,
)
from contexts.tenancy.domain.tenant_id import TenantId
from padhanam.observability.security_events import SecurityEventLogger
from padhanam.security import Principal


async def get_tenant_session_factory(
    *,
    cache: TenantSessionFactoryCache,
    registry,
    security_events: SecurityEventLogger,
    tenant_id: TenantId,
    principal: Principal,
) -> async_sessionmaker[AsyncSession]:
    """Return the per-tenant ``async_sessionmaker`` for ``tenant_id``.

    Operator-context required; tenant-context callers raise
    ``AuthorizationError`` at the use-case policy boundary inside
    ``reveal_connection_config``.
    """
    return await cache.get(
        tenant_id=tenant_id,
        principal=principal,
        registry=registry,
        security_events=security_events,
    )


async def invalidate_tenant_session_factory(
    *,
    cache: TenantSessionFactoryCache,
    tenant_id: TenantId,
) -> None:
    """Dispose the cached engine for ``tenant_id`` and remove the entry."""
    await cache.invalidate(tenant_id)


__all__ = [
    "TenantSessionFactoryCache",
    "get_tenant",
    "get_tenant_session_factory",
    "invalidate_tenant_session_factory",
    "list_tenants",
    "register_tenant",
    "reveal_connection_config",
    "update_tenant_status",
]
