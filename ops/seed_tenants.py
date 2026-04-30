"""Register the test-set tenants in the registry (D32, D36).

The two test tenants ``a`` and ``b`` correspond to the
``postgres-tenant-a`` and ``postgres-tenant-b`` Compose services
landed at S9. Connection configs reference them by their Compose
service hostnames; this script must run inside the ``vadakkan-api``
container so those hostnames resolve.

Idempotent: if a tenant id already exists in the registry, the script
skips it and logs the no-op. Re-running is a no-op.

Test-set tenant ids are deterministic so subsequent sessions and
tests can reference them without lookups:

  - tenant-a UUID: ``00000000-0000-4000-8000-00000000a001``
  - tenant-b UUID: ``00000000-0000-4000-8000-00000000b002``

These are the same UUIDs used in the ``test_registry_isolation``
contract test and form the canonical test set for P3.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from contexts.audit.adapters.outbound.noop import NoOpAuditAdapter
from contexts.tenancy.adapters.outbound.postgres.registry import (
    PostgresTenantRegistry,
)
from contexts.tenancy.application import OPERATOR_ROLE, register_tenant
from contexts.tenancy.domain import TenantConnectionConfig, TenantId
from shared_kernel import Jurisdiction, TenantId as SharedTenantId
from vadakkan.config import ControlPlaneSettings, TenantPostgresSettings
from vadakkan.observability.security_events import SecurityEvent
from vadakkan.security import Principal


# Deterministic test-set tenant ids. These are wired into the
# integration tests at tests/integration/contexts/tenancy/.
TENANT_A_UUID = "00000000-0000-4000-8000-00000000a001"
TENANT_B_UUID = "00000000-0000-4000-8000-00000000b002"


def _operator_principal() -> Principal:
    return Principal(
        subject="system:control_plane",
        tenant_id=SharedTenantId("operator"),
        roles=frozenset({OPERATOR_ROLE}),
        credential_ref="dev-token-op...",
    )


class _StdoutSecurityEvents:
    def emit(self, event: SecurityEvent) -> None:
        logging.getLogger("ops.seed_tenants").info(
            "security_event category=%s action=%s outcome=%s",
            event.category,
            event.action,
            event.outcome,
        )


async def _seed() -> None:
    log = logging.getLogger("ops.seed_tenants")
    registry = PostgresTenantRegistry.from_settings(
        settings=ControlPlaneSettings(),
        audit=NoOpAuditAdapter(),
        security_events=_StdoutSecurityEvents(),
    )
    try:
        existing = {str(t.id) for t in await registry.list_tenants()}

        targets = [
            (
                TENANT_A_UUID,
                "Tenant A",
                Jurisdiction("eu-west"),
                TenantPostgresSettings.for_tenant("a"),
            ),
            (
                TENANT_B_UUID,
                "Tenant B",
                Jurisdiction("us-east"),
                TenantPostgresSettings.for_tenant("b"),
            ),
        ]

        principal = _operator_principal()
        sec = _StdoutSecurityEvents()

        for tenant_uuid, display_name, jurisdiction, settings in targets:
            if tenant_uuid in existing:
                log.info("skipping %s — already registered", tenant_uuid)
                continue
            plaintext = TenantConnectionConfig(
                host=settings.host,
                port=settings.port,
                username=settings.user,
                password=settings.password,
                database=settings.db,
            )
            await register_tenant(
                principal=principal,
                registry=registry,
                security_events=sec,
                tenant_id=TenantId(tenant_uuid),
                jurisdiction=jurisdiction,
                display_name=display_name,
                connection_config=plaintext,
            )
            log.info("registered %s (%s)", tenant_uuid, display_name)
    finally:
        await registry.dispose()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    asyncio.run(_seed())
    return 0


if __name__ == "__main__":
    sys.exit(main())
