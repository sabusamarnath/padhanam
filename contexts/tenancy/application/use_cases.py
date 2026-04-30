"""Tenancy use cases (D34).

The use cases live above the registry port and enforce policy. They
accept a Principal as the caller context and either permit, deny, or
require operator context for credential-revealing operations. Calls
to the registry port flow through here in production code; tests
that exercise the adapter directly bypass policy by construction.

Operator-context predicate
--------------------------
The S11 connection-resolution layer runs as a system actor with
role ``OPERATOR_ROLE`` carried on its Principal. ``is_operator(p)``
returns True iff that role is present. Tenant-context callers carry
their own roles (e.g. ``"audit.read"``) but not the operator role.

Policy boundary
---------------
- ``register_tenant``, ``get_tenant``, ``list_tenants``,
  ``update_tenant_status``: operator-context required for register
  and update (control-plane is operator-administered per D33);
  tenant-context allowed for get/list of tenants in their own
  jurisdiction (read of the encrypted form is safe).
- ``reveal_connection_config``: operator-context only. Rejects all
  tenant-context callers (own-tenant included) per D34 — no use case
  has demanded tenant-self-credential-read, and the reversibility of
  adding the boundary later is cheaper than removing it.

Denials raise ``AuthorizationError`` and emit a security event
(``authz_denial``).
"""

from __future__ import annotations

from typing import Protocol

from contexts.tenancy.domain.tenant import Tenant, TenantStatus
from contexts.tenancy.domain.tenant_connection_config import TenantConnectionConfig
from contexts.tenancy.domain.tenant_id import TenantId
from contexts.tenancy.ports import TenantRegistryPort
from shared_kernel import Jurisdiction
from vadakkan.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
    SecurityEventLogger,
)
from vadakkan.security import AuthorizationError, Principal

OPERATOR_ROLE = "vadakkan.operator"


def is_operator(principal: Principal) -> bool:
    """Operator-context predicate.

    A principal is operator-context iff it carries the operator role.
    Tenant-context callers carry their own roles but not this one.
    """
    return OPERATOR_ROLE in principal.roles


class _AsyncRegistryPort(Protocol):
    """The async shape of TenantRegistryPort the adapter exposes.

    The S9 port Protocol is synchronous-shaped because it predates the
    async adapter. The S10 adapter implements the methods as
    coroutines; the use cases call them with await. A future S11
    cleanup may replace the synchronous Protocol with an async one;
    until then this private Protocol documents the actual shape.
    """

    async def register_tenant(
        self,
        tenant_id: TenantId,
        jurisdiction: Jurisdiction,
        display_name: str,
        connection_config: TenantConnectionConfig,
    ) -> Tenant: ...

    async def get_tenant(self, tenant_id: TenantId) -> Tenant | None: ...

    async def list_tenants(
        self, jurisdiction: Jurisdiction | None = None
    ) -> list[Tenant]: ...

    async def update_tenant_status(
        self, tenant_id: TenantId, status: TenantStatus
    ) -> Tenant: ...

    async def reveal_connection_config(
        self, tenant_id: TenantId
    ) -> TenantConnectionConfig: ...


def _deny(
    *,
    principal: Principal,
    action: str,
    tenant_id: TenantId,
    security_events: SecurityEventLogger,
) -> AuthorizationError:
    security_events.emit(
        SecurityEvent(
            category=SecurityEventCategory.AUTHZ_DENIAL,
            principal_ref=principal.subject,
            tenant_id=str(principal.tenant_id),
            action=action,
            resource_ref=f"tenant:{tenant_id}",
            outcome="deny",
        )
    )
    return AuthorizationError(
        f"{action} requires operator context; "
        f"principal {principal.subject!r} denied"
    )


async def register_tenant(
    *,
    principal: Principal,
    registry: _AsyncRegistryPort,
    security_events: SecurityEventLogger,
    tenant_id: TenantId,
    jurisdiction: Jurisdiction,
    display_name: str,
    connection_config: TenantConnectionConfig,
) -> Tenant:
    if not is_operator(principal):
        raise _deny(
            principal=principal,
            action="tenant.register",
            tenant_id=tenant_id,
            security_events=security_events,
        )
    return await registry.register_tenant(
        tenant_id=tenant_id,
        jurisdiction=jurisdiction,
        display_name=display_name,
        connection_config=connection_config,
    )


async def get_tenant(
    *,
    principal: Principal,
    registry: _AsyncRegistryPort,
    security_events: SecurityEventLogger,
    tenant_id: TenantId,
) -> Tenant | None:
    # Read of the encrypted form is safe for any authenticated caller;
    # cross-tenant reads are scoped at the adapter layer in S11+ when
    # the routing context is real.
    return await registry.get_tenant(tenant_id)


async def list_tenants(
    *,
    principal: Principal,
    registry: _AsyncRegistryPort,
    security_events: SecurityEventLogger,
    jurisdiction: Jurisdiction | None = None,
) -> list[Tenant]:
    return await registry.list_tenants(jurisdiction=jurisdiction)


async def update_tenant_status(
    *,
    principal: Principal,
    registry: _AsyncRegistryPort,
    security_events: SecurityEventLogger,
    tenant_id: TenantId,
    status: TenantStatus,
    session_factory_cache: "_InvalidatableCache | None" = None,
) -> Tenant:
    if not is_operator(principal):
        raise _deny(
            principal=principal,
            action="tenant.update_status",
            tenant_id=tenant_id,
            security_events=security_events,
        )
    tenant = await registry.update_tenant_status(tenant_id, status)
    # Per D36, any status transition invalidates the cached per-tenant
    # session factory. Wired here at the application layer rather than
    # in the registry adapter because cache lifecycle is application
    # concern; the cache itself is optional so this use case still
    # works under unit-test wiring that does not construct the cache.
    if session_factory_cache is not None:
        await session_factory_cache.invalidate(tenant_id)
    return tenant


class _InvalidatableCache(Protocol):
    async def invalidate(self, tenant_id: TenantId) -> None: ...


async def reveal_connection_config(
    *,
    principal: Principal,
    registry: _AsyncRegistryPort,
    security_events: SecurityEventLogger,
    tenant_id: TenantId,
) -> TenantConnectionConfig:
    """Operator-context only. Rejects all tenant-context callers (D34)."""
    if not is_operator(principal):
        raise _deny(
            principal=principal,
            action="tenant.reveal_credentials",
            tenant_id=tenant_id,
            security_events=security_events,
        )
    security_events.emit(
        SecurityEvent(
            category=SecurityEventCategory.PRIVILEGED_ACTION,
            principal_ref=principal.subject,
            tenant_id=None,
            action="tenant.reveal_credentials",
            resource_ref=f"tenant:{tenant_id}",
            outcome="allow",
        )
    )
    return await registry.reveal_connection_config(tenant_id)
