"""End-to-end integration test for the per-tenant routing layer (D36).

Exercises the full slice — registry → reveal_connection_config →
session factory → live SQL against the per-tenant tenant_audit table —
against the loopback-bound control-plane Postgres instance from S10
(the deliberate dev-only host-port-binding exception).

Topology note: the test's "tenant" databases live on the
postgres-control-plane Postgres instance because the host pytest
process can only reach loopback-bound services (S5 rule). The
postgres-tenant-a and postgres-tenant-b instances only resolve on the
Compose-internal network, so the seeded tenants registered by
``make seed-tenants`` are not directly reachable here. The test
creates its own tenants with loopback-routed connections, applies the
per-tenant Alembic migration to those test databases, and tears them
down at the end. The seeded tenants from ``make seed-tenants`` live
in the registry undisturbed.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from contexts.audit.adapters.outbound.noop import NoOpAuditAdapter
from contexts.tenancy.adapters.outbound.postgres.registry import (
    PostgresTenantRegistry,
    tenant_registry,
)
from contexts.tenancy.adapters.outbound.sqlalchemy.session_factory import (
    SqlAlchemyTenantSessionFactory,
)
from contexts.tenancy.application import (
    OPERATOR_ROLE,
    TenantSessionFactoryCache,
    register_tenant,
    update_tenant_status,
)
from contexts.tenancy.domain import (
    TenantConnectionConfig,
    TenantId,
    TenantStatus,
)
from shared_kernel import Jurisdiction, TenantId as SharedTenantId
from padhanam.config import ControlPlaneSettings
from padhanam.observability.security_events import SecurityEvent
from padhanam.security import Principal


CONTROL_PLANE_HOST = os.environ.get("CONTROL_PLANE_HOST_OVERRIDE", "127.0.0.1")
CONTROL_PLANE_PORT = int(os.environ.get("CONTROL_PLANE_PORT_OVERRIDE", "5433"))


def _operator() -> Principal:
    return Principal(
        subject="system:control_plane",
        tenant_id=SharedTenantId("operator"),
        roles=frozenset({OPERATOR_ROLE}),
        credential_ref="dev-token-op...",
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
def e2e_setup(event_loop):
    """Create two test databases on the loopback-bound control-plane
    instance, apply the per-tenant migration to each, register two
    tenants in the registry pointing at them, and yield (registry,
    cache, sec, tenant_a_id, tenant_b_id). Teardown drops the test
    databases and clears the registry rows.
    """
    base = ControlPlaneSettings()
    cp_settings = ControlPlaneSettings(
        user=base.user,
        password=base.password,
        db=base.db,
        host=CONTROL_PLANE_HOST,
        port=CONTROL_PLANE_PORT,
    )

    e2e_suffix = uuid.uuid4().hex[:8]
    tenant_a_db = f"e2e_tenant_a_{e2e_suffix}"
    tenant_b_db = f"e2e_tenant_b_{e2e_suffix}"
    tenant_a_uuid = f"00000000-0000-4000-8000-{e2e_suffix:>012}"
    tenant_b_uuid = "00000000-0000-4000-8000-" + e2e_suffix.rjust(11, "0") + "f"

    sync_url = (
        f"postgresql+psycopg://{cp_settings.user}:{cp_settings.password}"
        f"@{cp_settings.host}:{cp_settings.port}/{cp_settings.db}"
    )

    # Step 1: create two databases on the control-plane instance.
    admin_engine = sa.create_engine(sync_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            for db_name in (tenant_a_db, tenant_b_db):
                conn.execute(sa.text(f'CREATE DATABASE "{db_name}"'))
    except Exception as e:
        admin_engine.dispose()
        pytest.skip(f"control-plane Postgres unreachable: {e}")

    # Step 2: apply the per-tenant migration to each test database.
    for db_name in (tenant_a_db, tenant_b_db):
        per_db_url = (
            f"postgresql+psycopg://{cp_settings.user}:{cp_settings.password}"
            f"@{cp_settings.host}:{cp_settings.port}/{db_name}"
        )
        cfg = Config("alembic.ini", ini_section="tenant")
        cfg.set_main_option("sqlalchemy.url", per_db_url)
        command.upgrade(cfg, "head")

    # Step 3: stand up the registry adapter against control-plane.
    sec = _CollectingSecurityEvents()
    registry = PostgresTenantRegistry.from_settings(
        settings=cp_settings,
        audit=NoOpAuditAdapter(),
        security_events=sec,
    )

    # Step 4: register the two test tenants.
    async def register() -> None:
        for tenant_uuid, db_name, jurisdiction in (
            (tenant_a_uuid, tenant_a_db, Jurisdiction("eu-west")),
            (tenant_b_uuid, tenant_b_db, Jurisdiction("us-east")),
        ):
            await register_tenant(
                principal=_operator(),
                registry=registry,
                security_events=sec,
                tenant_id=TenantId(tenant_uuid),
                jurisdiction=jurisdiction,
                display_name=f"e2e {tenant_uuid}",
                connection_config=TenantConnectionConfig(
                    host=CONTROL_PLANE_HOST,
                    port=CONTROL_PLANE_PORT,
                    username=cp_settings.user,
                    password=cp_settings.password,
                    database=db_name,
                ),
            )

    event_loop.run_until_complete(register())
    sec.events.clear()

    cache = TenantSessionFactoryCache(SqlAlchemyTenantSessionFactory())

    try:
        yield registry, cache, sec, TenantId(tenant_a_uuid), TenantId(tenant_b_uuid)
    finally:
        async def cleanup() -> None:
            await cache.dispose_all()
            async with registry._sessionmaker() as session:
                await session.execute(
                    sa.delete(tenant_registry).where(
                        tenant_registry.c.tenant_id.in_(
                            [tenant_a_uuid, tenant_b_uuid]
                        )
                    )
                )
                await session.commit()
            await registry.dispose()
        event_loop.run_until_complete(cleanup())
        with admin_engine.connect() as conn:
            for db_name in (tenant_a_db, tenant_b_db):
                conn.execute(
                    sa.text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :db AND pid <> pg_backend_pid()"
                    ),
                    {"db": db_name},
                )
                conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{db_name}"'))
        admin_engine.dispose()


def test_factory_opens_session_against_migrated_tenant(event_loop, e2e_setup) -> None:
    """Cache miss → factory constructs engine → session executes a real query."""
    registry, cache, sec, tenant_a_id, tenant_b_id = e2e_setup

    async def run() -> None:
        sm = await cache.get(
            tenant_id=tenant_a_id,
            principal=_operator(),
            registry=registry,
            security_events=sec,
        )
        async with sm() as session:
            result = await session.execute(
                sa.text("SELECT COUNT(*) FROM tenant_audit")
            )
            assert result.scalar() == 0

    event_loop.run_until_complete(run())


def test_factory_repeats_for_second_tenant(event_loop, e2e_setup) -> None:
    """Each tenant resolves to its own engine + database."""
    registry, cache, sec, tenant_a_id, tenant_b_id = e2e_setup

    async def run() -> None:
        sm_a = await cache.get(
            tenant_id=tenant_a_id,
            principal=_operator(),
            registry=registry,
            security_events=sec,
        )
        sm_b = await cache.get(
            tenant_id=tenant_b_id,
            principal=_operator(),
            registry=registry,
            security_events=sec,
        )
        assert sm_a is not sm_b
        async with sm_b() as session:
            result = await session.execute(
                sa.text("SELECT COUNT(*) FROM tenant_audit")
            )
            assert result.scalar() == 0

    event_loop.run_until_complete(run())


def test_status_transition_invalidates_cache_against_live_db(
    event_loop, e2e_setup
) -> None:
    """update_tenant_status flushes the cache; subsequent get rebuilds.

    Suspension is a status, not a connectivity gate; the new session
    against the suspended tenant succeeds. Future work may add use-case
    level gating on suspended tenants.
    """
    registry, cache, sec, tenant_a_id, _ = e2e_setup

    async def run() -> None:
        sm_before = await cache.get(
            tenant_id=tenant_a_id,
            principal=_operator(),
            registry=registry,
            security_events=sec,
        )
        await update_tenant_status(
            principal=_operator(),
            registry=registry,
            security_events=sec,
            tenant_id=tenant_a_id,
            status=TenantStatus.SUSPENDED,
            session_factory_cache=cache,
        )
        sm_after = await cache.get(
            tenant_id=tenant_a_id,
            principal=_operator(),
            registry=registry,
            security_events=sec,
        )
        assert sm_after is not sm_before
        async with sm_after() as session:
            result = await session.execute(
                sa.text("SELECT COUNT(*) FROM tenant_audit")
            )
            assert result.scalar() == 0

    event_loop.run_until_complete(run())
