"""Register the dogfood personal tenant in the control plane ([dogfood-setup], D32, D36).

Ops-only, no domain code: this mirrors ``ops/seed_tenants.py`` but
registers a single dedicated tenant for the operator's personal
dogfooding data, kept out of the deterministic ``a``/``b`` test set so
the test fixtures stay clean. The connection config references the
``postgres-tenant-personal`` Compose service by hostname, so this must
run inside the ``padhanam-api`` container (via ``make dogfood-provision``)
where that hostname resolves and ``POSTGRES_TENANT_PERSONAL_*`` is set.

Idempotent: if the personal tenant id already exists in the registry,
the script skips it and logs the no-op. Re-running is a no-op (re-running
after a wipe re-registers nothing — the registry row survives a
database wipe; only the tenant's data plane is recreated, which
``make migrate`` then re-migrates).

The id is a neutral, deterministic placeholder — it encodes no real
identity:

  - personal tenant UUID: ``00000000-0000-4000-8000-00000000d001`` ("d" = dogfood)
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
from padhanam.config import ControlPlaneSettings, TenantPostgresSettings
from padhanam.observability.security_events import SecurityEvent
from padhanam.security import Principal


# Neutral, deterministic dogfood tenant id — encodes no real identity.
PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"
PERSONAL_TENANT_LABEL = "personal"
PERSONAL_TENANT_DISPLAY = "Dogfood (personal)"
PERSONAL_TENANT_JURISDICTION = "eu-west"


def _operator_principal() -> Principal:
    return Principal(
        subject="migration:ops/dogfood_provision",
        tenant_id=SharedTenantId("operator"),
        roles=frozenset({OPERATOR_ROLE}),
        credential_ref="dev-token-op...",
    )


class _StdoutSecurityEvents:
    def emit(self, event: SecurityEvent) -> None:
        logging.getLogger("ops.dogfood_provision").info(
            "security_event category=%s action=%s outcome=%s",
            event.category,
            event.action,
            event.outcome,
        )


async def _provision() -> None:
    log = logging.getLogger("ops.dogfood_provision")
    registry = PostgresTenantRegistry.from_settings(
        settings=ControlPlaneSettings(),
        audit=NoOpAuditAdapter(),
        security_events=_StdoutSecurityEvents(),
    )
    try:
        existing = {str(t.id) for t in await registry.list_tenants()}
        if PERSONAL_TENANT_UUID in existing:
            log.info(
                "skipping %s — already registered", PERSONAL_TENANT_UUID
            )
            return

        settings = TenantPostgresSettings.for_tenant(PERSONAL_TENANT_LABEL)
        plaintext = TenantConnectionConfig(
            host=settings.host,
            port=settings.port,
            username=settings.user,
            password=settings.password,
            database=settings.db,
        )
        await register_tenant(
            principal=_operator_principal(),
            registry=registry,
            security_events=_StdoutSecurityEvents(),
            tenant_id=TenantId(PERSONAL_TENANT_UUID),
            jurisdiction=Jurisdiction(PERSONAL_TENANT_JURISDICTION),
            display_name=PERSONAL_TENANT_DISPLAY,
            connection_config=plaintext,
        )
        log.info(
            "registered %s (%s) -> %s:%s/%s",
            PERSONAL_TENANT_UUID,
            PERSONAL_TENANT_DISPLAY,
            settings.host,
            settings.port,
            settings.db,
        )
    finally:
        await registry.dispose()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    asyncio.run(_provision())
    return 0


if __name__ == "__main__":
    sys.exit(main())
