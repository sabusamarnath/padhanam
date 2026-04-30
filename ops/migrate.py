"""Two-phase migration runner (D36).

Phase 1: control-plane migrations via the existing
`alembic --name control_plane upgrade head` invocation against the
dedicated `postgres-control-plane` instance (D33).

Phase 2: per-tenant migrations. Iterates over registered tenants in
the registry, resolves each tenant's connection string via
`reveal_connection_config` as an operator-context system actor, and
runs the per-tenant Alembic track against each database.

Per-tenant transactional (D36): failure on tenant B leaves tenant A
migrated and tenant B at its prior version; the runner raises and
exits non-zero. Re-running the runner resumes from tenant B (Alembic
is idempotent on already-applied revisions). No cross-tenant
atomicity at the migration layer — D32 commits to per-tenant instance
independence which forecloses two-phase commit or distributed
transactions.

Idempotency: re-running after no schema changes is a no-op via
Alembic's `alembic_version` table.

Security events: emits a `privileged_action` event per tenant
migration completion with `action=tenant.migrate` so operator-driven
schema changes are auditable.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from alembic import command
from alembic.config import Config

from contexts.audit.adapters.outbound.noop import NoOpAuditAdapter
from contexts.tenancy.adapters.outbound.postgres.registry import (
    PostgresTenantRegistry,
)
from contexts.tenancy.application import OPERATOR_ROLE, list_tenants, reveal_connection_config
from contexts.tenancy.domain.tenant_connection_config import TenantConnectionConfig
from shared_kernel import TenantId as SharedTenantId
from vadakkan.config import ControlPlaneSettings
from vadakkan.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
)
from vadakkan.security import Principal

log = logging.getLogger("ops.migrate")


def _operator_principal() -> Principal:
    return Principal(
        subject="system:control_plane",
        tenant_id=SharedTenantId("operator"),
        roles=frozenset({OPERATOR_ROLE}),
        credential_ref="dev-token-op...",
    )


class _StdoutSecurityEvents:
    def emit(self, event: SecurityEvent) -> None:
        log.info(
            "security_event category=%s action=%s tenant=%s outcome=%s",
            event.category,
            event.action,
            event.tenant_id,
            event.outcome,
        )


def _run_control_plane_phase() -> None:
    log.info("phase 1: control-plane migrations")
    cfg = Config("alembic.ini", ini_section="control_plane")
    command.upgrade(cfg, "head")
    log.info("phase 1: complete")


def _tenant_sync_url(plaintext: TenantConnectionConfig) -> str:
    """Synchronous DSN for Alembic. Alembic env.py is sync (D34)."""
    return (
        f"postgresql+psycopg://{plaintext.username}:{plaintext.password}"
        f"@{plaintext.host}:{plaintext.port}/{plaintext.database}"
    )


def _run_tenant_migration(plaintext: TenantConnectionConfig) -> None:
    cfg = Config("alembic.ini", ini_section="tenant")
    cfg.set_main_option("sqlalchemy.url", _tenant_sync_url(plaintext))
    command.upgrade(cfg, "head")


async def _run_per_tenant_phase() -> None:
    log.info("phase 2: per-tenant migrations")
    sec = _StdoutSecurityEvents()
    principal = _operator_principal()
    registry = PostgresTenantRegistry.from_settings(
        settings=ControlPlaneSettings(),
        audit=NoOpAuditAdapter(),
        security_events=sec,
    )
    try:
        tenants = await list_tenants(
            principal=principal,
            registry=registry,
            security_events=sec,
        )
        log.info("phase 2: %d tenant(s) to migrate", len(tenants))
        for tenant in tenants:
            log.info("phase 2: migrating tenant %s (%s)", tenant.id, tenant.display_name)
            plaintext = await reveal_connection_config(
                principal=principal,
                registry=registry,
                security_events=sec,
                tenant_id=tenant.id,
            )
            _run_tenant_migration(plaintext)
            sec.emit(
                SecurityEvent(
                    category=SecurityEventCategory.PRIVILEGED_ACTION,
                    principal_ref=principal.subject,
                    tenant_id=str(tenant.id),
                    action="tenant.migrate",
                    resource_ref=f"tenant:{tenant.id}",
                    outcome="allow",
                )
            )
            log.info("phase 2: tenant %s migrated", tenant.id)
    finally:
        await registry.dispose()
    log.info("phase 2: complete")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    # Alembic's fileConfig (called from each env.py) resets the root
    # logger level to WARN per alembic.ini's [logger_root]. Pin the
    # runner's own logger to INFO so progress messages survive across
    # control-plane and per-tenant phases.
    log.setLevel(logging.INFO)
    _run_control_plane_phase()
    asyncio.run(_run_per_tenant_phase())
    return 0


if __name__ == "__main__":
    sys.exit(main())
