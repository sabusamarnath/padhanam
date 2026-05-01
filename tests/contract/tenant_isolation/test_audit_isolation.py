"""Tenant isolation contract tests for the audit context (D24, D35, D37).

Two layers:

1. Policy-decision tests (S5 baseline) — assert the cross-tenant
   permission decisions the policy module makes for audit-typed
   resources. Necessary at the policy boundary; trivial against the
   no-op adapter from P2.

2. Adapter-level tests (S12) — assert that the Postgres audit
   adapter's destination routing isolates per-tenant chains and
   prevents accidental cross-destination writes via schema-layer
   CHECK constraints. Five red-team scenarios:

   2a. Tenant A's event lands on tenant A's database, not on tenant B
       or the control plane.
   2b. Tenant B's event lands on tenant B's database, not on tenant A
       or the control plane.
   2c. Empty-string sentinel routes the event to the control-plane
       audit table; per-tenant tables remain empty.
   2d. Tenant A's chain and tenant B's chain advance independently —
       per-destination chain commitment from D35.
   2e. Cross-destination CHECK constraints raise on accidental sentinel
       mix-up: empty-string into a per-tenant table or non-empty into
       the control-plane table both fail at the schema layer.

Topology note: the adapter-level tests create two synthetic per-tenant
databases on the loopback-bound control-plane Postgres instance (the
S5 host-port-binding exception). The seeded tenants registered by
``make seed-tenants`` live on Compose-internal-only Postgres instances
and are not directly reachable from host pytest; the adapter's
destination routing is database-agnostic at the application layer,
which is what these tests assert.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from contexts.audit.adapters.outbound.postgres.audit import (
    PostgresAuditAdapter,
    tenant_audit,
)
from contexts.audit.domain.events import AuditEvent, GENESIS_HASH
from shared_kernel import TenantId
from padhanam.config import ControlPlaneSettings
from padhanam.security.auth import Principal
from padhanam.security.policy import Decision, Resource, check


# --------------------------------------------------------------------
# Layer 1: policy-decision tests (S5 baseline).
# --------------------------------------------------------------------


def test_principal_a_cannot_read_tenant_b_audit_event(
    tenant_a_principal: Principal,
) -> None:
    cross_tenant_resource = Resource(
        type="audit_event",
        id="event-from-tenant-b",
        tenant_id=TenantId("tenant-b"),
    )
    decision = check(tenant_a_principal, "audit.read", cross_tenant_resource)
    assert decision is Decision.DENY


def test_principal_b_cannot_write_to_tenant_a_audit_chain(
    tenant_b_principal: Principal,
) -> None:
    cross_tenant_resource = Resource(
        type="audit_event",
        id="event-from-tenant-a",
        tenant_id=TenantId("tenant-a"),
    )
    decision = check(tenant_b_principal, "audit.write", cross_tenant_resource)
    assert decision is Decision.DENY


def test_principal_can_read_own_tenant_audit_event(
    tenant_a_principal: Principal,
) -> None:
    own_resource = Resource(
        type="audit_event",
        id="event-own",
        tenant_id=TenantId("tenant-a"),
    )
    decision = check(tenant_a_principal, "audit.read", own_resource)
    assert decision is Decision.ALLOW


# --------------------------------------------------------------------
# Layer 2: adapter-level isolation tests (S12).
# --------------------------------------------------------------------


CONTROL_PLANE_HOST = os.environ.get("CONTROL_PLANE_HOST_OVERRIDE", "127.0.0.1")
CONTROL_PLANE_PORT = int(os.environ.get("CONTROL_PLANE_PORT_OVERRIDE", "5433"))


def _cp_settings() -> ControlPlaneSettings:
    base = ControlPlaneSettings()
    return ControlPlaneSettings(
        user=base.user,
        password=base.password,
        db=base.db,
        host=CONTROL_PLANE_HOST,
        port=CONTROL_PLANE_PORT,
    )


def _sync_url(settings: ControlPlaneSettings, db: str | None = None) -> str:
    return (
        f"postgresql+psycopg://{settings.user}:{settings.password}"
        f"@{settings.host}:{settings.port}/{db or settings.db}"
    )


def _async_url(settings: ControlPlaneSettings, db: str | None = None) -> str:
    return (
        f"postgresql+asyncpg://{settings.user}:{settings.password}"
        f"@{settings.host}:{settings.port}/{db or settings.db}"
    )


def _event(*, tenant_id: str, action: str = "test.write") -> AuditEvent:
    """Build an event with draft chain hashes; the adapter recomputes."""
    return AuditEvent(
        actor="system:test",
        tenant_id=tenant_id,
        jurisdiction="test",
        action_verb=action,
        resource_type="probe",
        resource_id="r1",
        before_state={},
        after_state={"k": "v"},
        correlation_id="",
        previous_event_hash=GENESIS_HASH,
        this_event_hash="",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@pytest.fixture(scope="module")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture
def isolation_setup(event_loop):
    """Provision control-plane + two synthetic per-tenant databases on
    the loopback control-plane instance, apply migrations, and yield
    (adapter, tenant_a_id, tenant_b_id, tenant_a_sm, tenant_b_sm,
    cp_sm). Teardown drops the per-tenant databases and clears any
    control-plane test rows."""
    settings = _cp_settings()
    suffix = uuid.uuid4().hex[:8]
    tenant_a_db = f"audit_iso_a_{suffix}"
    tenant_b_db = f"audit_iso_b_{suffix}"
    tenant_a_uuid = "00000000-0000-4000-8000-" + suffix.rjust(11, "0") + "a"
    tenant_b_uuid = "00000000-0000-4000-8000-" + suffix.rjust(11, "0") + "b"

    sync_engine = sa.create_engine(
        _sync_url(settings), isolation_level="AUTOCOMMIT"
    )
    try:
        with sync_engine.connect() as conn:
            for db in (tenant_a_db, tenant_b_db):
                conn.execute(sa.text(f'CREATE DATABASE "{db}"'))
    except Exception as e:
        sync_engine.dispose()
        pytest.skip(f"control-plane Postgres unreachable: {e}")

    for db in (tenant_a_db, tenant_b_db):
        cfg = Config("alembic.ini", ini_section="tenant")
        cfg.set_main_option("sqlalchemy.url", _sync_url(settings, db))
        command.upgrade(cfg, "head")

    cp_engine = create_async_engine(_async_url(settings))
    tenant_a_engine = create_async_engine(_async_url(settings, tenant_a_db))
    tenant_b_engine = create_async_engine(_async_url(settings, tenant_b_db))
    tenant_a_sm = async_sessionmaker(tenant_a_engine, expire_on_commit=False)
    tenant_b_sm = async_sessionmaker(tenant_b_engine, expire_on_commit=False)
    cp_sm = async_sessionmaker(cp_engine, expire_on_commit=False)

    sm_by_id = {tenant_a_uuid: tenant_a_sm, tenant_b_uuid: tenant_b_sm}

    async def resolver(tenant_id: TenantId) -> async_sessionmaker[AsyncSession]:
        sm = sm_by_id.get(str(tenant_id))
        if sm is None:
            raise LookupError(f"unexpected tenant_id {tenant_id!r}")
        return sm

    adapter = PostgresAuditAdapter(
        control_plane_engine=cp_engine,
        per_tenant_sessionmaker_resolver=resolver,
    )

    try:
        yield (
            adapter,
            TenantId(tenant_a_uuid),
            TenantId(tenant_b_uuid),
            tenant_a_sm,
            tenant_b_sm,
            cp_sm,
        )
    finally:
        async def cleanup() -> None:
            async with cp_sm() as session:
                await session.execute(sa.delete(tenant_audit))
                await session.commit()
            await adapter.dispose()
            await tenant_a_engine.dispose()
            await tenant_b_engine.dispose()
        event_loop.run_until_complete(cleanup())
        with sync_engine.connect() as conn:
            for db in (tenant_a_db, tenant_b_db):
                conn.execute(
                    sa.text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :db AND pid <> pg_backend_pid()"
                    ),
                    {"db": db},
                )
                conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{db}"'))
        sync_engine.dispose()


def _row_count(event_loop, sm) -> int:
    async def run() -> int:
        async with sm() as session:
            return (
                await session.execute(sa.select(sa.func.count()).select_from(tenant_audit))
            ).scalar() or 0
    return event_loop.run_until_complete(run())


def test_tenant_a_event_isolated_to_tenant_a_database(
    event_loop, isolation_setup
) -> None:
    """Scenario 2a: a tenant-A event lands on postgres-tenant-a only;
    postgres-tenant-b and the control-plane stay empty."""
    adapter, tenant_a_id, tenant_b_id, sm_a, sm_b, sm_cp = isolation_setup

    event_loop.run_until_complete(
        adapter.emit(_event(tenant_id=str(tenant_a_id), action="tenant_a.action"))
    )

    assert _row_count(event_loop, sm_a) == 1
    assert _row_count(event_loop, sm_b) == 0
    assert _row_count(event_loop, sm_cp) == 0


def test_tenant_b_event_isolated_from_tenant_a(
    event_loop, isolation_setup
) -> None:
    """Scenario 2b: a tenant-B event lands on postgres-tenant-b only."""
    adapter, tenant_a_id, tenant_b_id, sm_a, sm_b, sm_cp = isolation_setup

    event_loop.run_until_complete(
        adapter.emit(_event(tenant_id=str(tenant_b_id), action="tenant_b.action"))
    )

    assert _row_count(event_loop, sm_b) == 1
    assert _row_count(event_loop, sm_a) == 0
    assert _row_count(event_loop, sm_cp) == 0


def test_control_plane_event_isolated_from_tenant_tables(
    event_loop, isolation_setup
) -> None:
    """Scenario 2c: an event with the empty-string sentinel lands on the
    control-plane tenant_audit table only."""
    adapter, _, _, sm_a, sm_b, sm_cp = isolation_setup

    event_loop.run_until_complete(
        adapter.emit(_event(tenant_id="", action="control_plane.action"))
    )

    assert _row_count(event_loop, sm_cp) == 1
    assert _row_count(event_loop, sm_a) == 0
    assert _row_count(event_loop, sm_b) == 0


def test_per_destination_chains_are_independent(
    event_loop, isolation_setup
) -> None:
    """Scenario 2d: tenant A's chain and tenant B's chain advance
    independently. Per-destination chain commitment from D35: writes
    to one destination do not affect another destination's chain.
    """
    adapter, tenant_a_id, tenant_b_id, sm_a, sm_b, _ = isolation_setup

    async def run() -> None:
        # Three writes to A, two to B, interleaved as (A, B, A, B, A).
        # Each destination's chain advances by exactly the writes
        # targeting it; cross-destination ordering cannot leak.
        await adapter.emit(_event(tenant_id=str(tenant_a_id), action="a.1"))
        await adapter.emit(_event(tenant_id=str(tenant_b_id), action="b.1"))
        await adapter.emit(_event(tenant_id=str(tenant_a_id), action="a.2"))
        await adapter.emit(_event(tenant_id=str(tenant_b_id), action="b.2"))
        await adapter.emit(_event(tenant_id=str(tenant_a_id), action="a.3"))

        async with sm_a() as session:
            a_rows = (
                await session.execute(
                    sa.select(
                        tenant_audit.c.previous_event_hash,
                        tenant_audit.c.this_event_hash,
                    ).order_by(tenant_audit.c.timestamp.asc(), tenant_audit.c.id.asc())
                )
            ).all()
        async with sm_b() as session:
            b_rows = (
                await session.execute(
                    sa.select(
                        tenant_audit.c.previous_event_hash,
                        tenant_audit.c.this_event_hash,
                    ).order_by(tenant_audit.c.timestamp.asc(), tenant_audit.c.id.asc())
                )
            ).all()

        # Chain shape: A has 3 rows chained genesis → r0 → r1; B has 2
        # rows chained genesis → r0.
        assert len(a_rows) == 3
        assert len(b_rows) == 2
        assert a_rows[0].previous_event_hash == GENESIS_HASH
        for i in range(1, 3):
            assert a_rows[i].previous_event_hash == a_rows[i - 1].this_event_hash
        assert b_rows[0].previous_event_hash == GENESIS_HASH
        assert b_rows[1].previous_event_hash == b_rows[0].this_event_hash

        # Critical isolation property: no row in B carries a hash from
        # A's chain as its previous_event_hash, and vice versa.
        a_hashes = {r.this_event_hash for r in a_rows}
        b_hashes = {r.this_event_hash for r in b_rows}
        assert a_hashes.isdisjoint(b_hashes)
        for row in b_rows:
            assert row.previous_event_hash not in a_hashes
        for row in a_rows:
            assert row.previous_event_hash not in b_hashes

    event_loop.run_until_complete(run())


def test_cross_destination_check_constraints_block_accidents(
    event_loop, isolation_setup
) -> None:
    """Scenario 2e: schema-layer CHECK constraints block cross-destination
    writes. Inserting a row with the empty-string sentinel into a
    per-tenant tenant_audit table raises an IntegrityError; symmetric
    on the control-plane side.
    """
    _, _, _, sm_a, _, sm_cp = isolation_setup

    base_values = {
        "actor": "system:test",
        "jurisdiction": "test",
        "timestamp": datetime.now(timezone.utc),
        "action_verb": "violation",
        "resource_type": "probe",
        "resource_id": "r1",
        "before_state": {},
        "after_state": {},
        "correlation_id": "",
        "previous_event_hash": GENESIS_HASH,
        "this_event_hash": "0" * 64,
    }

    async def violate_per_tenant_with_empty_sentinel() -> None:
        async with sm_a() as session:
            await session.execute(
                sa.insert(tenant_audit).values(tenant_id="", **base_values)
            )
            await session.commit()

    async def violate_control_plane_with_real_id() -> None:
        async with sm_cp() as session:
            await session.execute(
                sa.insert(tenant_audit).values(
                    tenant_id="00000000-0000-4000-8000-000000000001",
                    **base_values,
                )
            )
            await session.commit()

    with pytest.raises(IntegrityError):
        event_loop.run_until_complete(violate_per_tenant_with_empty_sentinel())
    with pytest.raises(IntegrityError):
        event_loop.run_until_complete(violate_control_plane_with_real_id())
