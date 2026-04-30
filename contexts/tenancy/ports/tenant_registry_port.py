"""TenantRegistryPort — the registry abstraction.

The tenancy registry is the source of truth for tenant identity,
jurisdiction, status, and the encrypted form of per-tenant database
credentials (D1, D12, D13, D21, D32, D33). Adapters land at S10
(control-plane Postgres adapter); S9 ships only the contract.

Contract notes:

- `register_tenant` accepts a *plaintext* `TenantConnectionConfig`. The
  port contract guarantees the implementation wraps the plaintext
  through `vadakkan/security/crypto.py` (D21 envelope encryption) before
  persistence. The returned Tenant carries `EncryptedCredentials`, never
  plaintext. The plaintext argument goes out of scope at the end of the
  call. The leak-prevention controls (logging filter, AST test, isolation
  test) land at S10 with the adapter; this port docstring is the
  contractual statement that justifies them.

- `get_tenant`, `list_tenants`, and the lifecycle method
  `update_tenant_status` never return plaintext credentials. The Tenant
  type they expose carries `EncryptedCredentials`. Routing adapters
  unwrap separately at the security boundary (S11).

- `list_tenants(jurisdiction=None)` enumerates all tenants. The optional
  filter narrows by jurisdiction; the registry itself is jurisdiction-
  spanning per D33 (control-plane is jurisdiction-spanning even though
  per-tenant data planes are jurisdiction-local).

The port is a Protocol so adapters need not inherit; satisfying the
methods is sufficient (consistent with the inference and observability
port shapes).
"""

from __future__ import annotations

from typing import Protocol

from shared_kernel import Jurisdiction

from contexts.tenancy.domain.tenant import Tenant, TenantStatus
from contexts.tenancy.domain.tenant_connection_config import TenantConnectionConfig
from contexts.tenancy.domain.tenant_id import TenantId


class TenantRegistryPort(Protocol):
    def register_tenant(
        self,
        tenant_id: TenantId,
        jurisdiction: Jurisdiction,
        display_name: str,
        connection_config: TenantConnectionConfig,
    ) -> Tenant: ...

    def get_tenant(self, tenant_id: TenantId) -> Tenant: ...

    def list_tenants(
        self, jurisdiction: Jurisdiction | None = None
    ) -> list[Tenant]: ...

    def update_tenant_status(
        self, tenant_id: TenantId, status: TenantStatus
    ) -> Tenant: ...
