"""Tests for the Postgres audit adapter (D22, D35, D37).

Exercises the adapter against the loopback-bound control-plane Postgres
instance (the deliberate dev-only host-port-binding exception from S5).
The control-plane track applies the control-plane ``tenant_audit``
migration; for the per-tenant destination, the test creates a fresh
database on the same instance, applies the per-tenant Alembic track to
it, and registers it as a synthetic "tenant" via a stub resolver. The
adapter is destination-agnostic at the application layer, which is
what these tests assert.
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
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from contexts.audit.adapters.outbound.postgres.audit import (
    PostgresAuditAdapter,
    tenant_audit,
)
from contexts.audit.domain.events import (
    AuditEvent,
    GENESIS_HASH,
    compute_event_hash,
)
from shared_kernel import TenantId
from padhanam.config import ControlPlaneSettings


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


def _make_event(
    *,
    tenant_id: str,
    action_verb: str = "test.write",
    timestamp: str | None = None,
    correlation_id: str = "",
    after_state: dict | None = None,
) -> AuditEvent:
    """Build an event with draft chain hashes; the adapter is chain
    authority and recomputes both fields inside its transaction (D37).
    The values passed here are placeholders the adapter overwrites.
    """
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    return AuditEvent(
        actor="system:test",
        tenant_id=tenant_id,
        jurisdiction="test",
        action_verb=action_verb,
        resource_type="probe",
        resource_id="r1",
        before_state={},
        after_state=after_state if after_state is not None else {"k": "v"},
        correlation_id=correlation_id,
        previous_event_hash=GENESIS_HASH,  # draft; adapter recomputes
        this_event_hash="",                 # draft; adapter recomputes
        timestamp=ts,
    )


@pytest.fixture(scope="module")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture
def adapter_setup(event_loop):
    """Provision the control-plane and a synthetic per-tenant database,
    apply migrations to each, and yield (adapter, tenant_a_id,
    tenant_a_sessionmaker) tuples plus a control-plane sessionmaker
    used for direct SELECTs in the test body. Teardown drops the
    per-tenant database and clears any test rows on the control-plane.
    """
    settings = _cp_settings()
    suffix = uuid.uuid4().hex[:8]
    tenant_db = f"audit_test_{suffix}"
    tenant_uuid = f"00000000-0000-4000-8000-{suffix:>012}"

    # Step 1: create the per-tenant database on the control-plane
    # instance (loopback-bound, dev-only host port exception from S5).
    sync_engine = sa.create_engine(
        _sync_url(settings), isolation_level="AUTOCOMMIT"
    )
    try:
        with sync_engine.connect() as conn:
            conn.execute(sa.text(f'CREATE DATABASE "{tenant_db}"'))
    except Exception as e:
        sync_engine.dispose()
        pytest.skip(f"control-plane Postgres unreachable: {e}")

    # Step 2: apply the per-tenant Alembic track to the new database.
    cfg = Config("alembic.ini", ini_section="tenant")
    cfg.set_main_option("sqlalchemy.url", _sync_url(settings, tenant_db))
    command.upgrade(cfg, "head")

    # Step 3: build async engines + sessionmakers for both destinations.
    cp_engine = create_async_engine(_async_url(settings))
    tenant_engine = create_async_engine(_async_url(settings, tenant_db))
    tenant_sm = async_sessionmaker(tenant_engine, expire_on_commit=False)

    async def resolver(tenant_id: TenantId) -> async_sessionmaker[AsyncSession]:
        if str(tenant_id) == tenant_uuid:
            return tenant_sm
        raise LookupError(f"unexpected tenant_id {tenant_id!r}")

    adapter = PostgresAuditAdapter(
        control_plane_engine=cp_engine,
        per_tenant_sessionmaker_resolver=resolver,
    )

    cp_sm = async_sessionmaker(cp_engine, expire_on_commit=False)

    try:
        yield adapter, TenantId(tenant_uuid), tenant_sm, cp_sm
    finally:
        async def cleanup() -> None:
            # Clear any control-plane rows produced by the test so the
            # control-plane chain stays empty for subsequent tests.
            async with cp_sm() as session:
                await session.execute(sa.delete(tenant_audit))
                await session.commit()
            await adapter.dispose()
            await tenant_engine.dispose()
        event_loop.run_until_complete(cleanup())
        with sync_engine.connect() as conn:
            conn.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :db AND pid <> pg_backend_pid()"
                ),
                {"db": tenant_db},
            )
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{tenant_db}"'))
        sync_engine.dispose()


def test_empty_sentinel_writes_to_control_plane(event_loop, adapter_setup) -> None:
    """A non-tenant event lands on the control-plane tenant_audit table
    and is absent from the per-tenant tenant_audit table."""
    adapter, tenant_a_id, tenant_sm, cp_sm = adapter_setup
    event = _make_event(tenant_id="")

    async def run() -> None:
        await adapter.emit(event)

        async with cp_sm() as session:
            cp_count = (
                await session.execute(sa.select(sa.func.count()).select_from(tenant_audit))
            ).scalar()
        async with tenant_sm() as session:
            tenant_count = (
                await session.execute(sa.select(sa.func.count()).select_from(tenant_audit))
            ).scalar()
        assert cp_count == 1
        assert tenant_count == 0

    event_loop.run_until_complete(run())


def test_non_empty_tenant_id_writes_to_routed_tenant(
    event_loop, adapter_setup
) -> None:
    """A tenant-scoped event lands on the routed tenant's tenant_audit
    table and is absent from the control-plane."""
    adapter, tenant_a_id, tenant_sm, cp_sm = adapter_setup
    event = _make_event(tenant_id=str(tenant_a_id))

    async def run() -> None:
        await adapter.emit(event)

        async with tenant_sm() as session:
            tenant_count = (
                await session.execute(sa.select(sa.func.count()).select_from(tenant_audit))
            ).scalar()
        async with cp_sm() as session:
            cp_count = (
                await session.execute(sa.select(sa.func.count()).select_from(tenant_audit))
            ).scalar()
        assert tenant_count == 1
        assert cp_count == 0

    event_loop.run_until_complete(run())


def test_consecutive_writes_form_a_chain(event_loop, adapter_setup) -> None:
    """Each row's previous_event_hash matches the prior row's
    this_event_hash, walking back to the genesis sentinel. The adapter
    is chain authority — callers' draft hashes are ignored."""
    adapter, tenant_a_id, tenant_sm, _ = adapter_setup

    async def run() -> None:
        for i in range(5):
            event = _make_event(
                tenant_id=str(tenant_a_id),
                action_verb=f"test.step{i}",
                timestamp=datetime(2026, 4, 30, 10, 0, i, tzinfo=timezone.utc).isoformat(),
            )
            await adapter.emit(event)

        async with tenant_sm() as session:
            rows = (
                await session.execute(
                    sa.select(
                        tenant_audit.c.previous_event_hash,
                        tenant_audit.c.this_event_hash,
                    ).order_by(tenant_audit.c.timestamp.asc())
                )
            ).all()

        assert len(rows) == 5
        # row 0 chains from genesis; row N chains from row N-1.
        assert rows[0].previous_event_hash == GENESIS_HASH
        for i in range(1, 5):
            assert rows[i].previous_event_hash == rows[i - 1].this_event_hash

    event_loop.run_until_complete(run())


def test_verify_chain_returns_intact_for_clean_chain(
    event_loop, adapter_setup
) -> None:
    """``verify_chain`` walks the destination chain and reports intact
    on a chain produced entirely through the adapter."""
    adapter, tenant_a_id, _, _ = adapter_setup

    async def run() -> None:
        for i in range(5):
            event = _make_event(
                tenant_id=str(tenant_a_id),
                action_verb=f"test.step{i}",
                timestamp=datetime(2026, 4, 30, 10, 1, i, tzinfo=timezone.utc).isoformat(),
            )
            await adapter.emit(event)

        result = await adapter.verify_chain(tenant_a_id)
        assert result.is_intact is True
        assert result.break_index is None
        assert result.length == 5

    event_loop.run_until_complete(run())


def test_verify_chain_detects_tampering(event_loop, adapter_setup) -> None:
    """A direct UPDATE that mutates a row's after_state without
    recomputing the chain hashes breaks the chain at the tampered row."""
    adapter, tenant_a_id, tenant_sm, _ = adapter_setup

    async def run() -> None:
        for i in range(5):
            event = _make_event(
                tenant_id=str(tenant_a_id),
                action_verb=f"test.step{i}",
                timestamp=datetime(2026, 4, 30, 10, 2, i, tzinfo=timezone.utc).isoformat(),
            )
            await adapter.emit(event)

        # Tamper with row 2's after_state in place; this changes the
        # payload that compute_event_hash would produce, but leaves the
        # stored this_event_hash unchanged.
        async with tenant_sm() as session:
            await session.execute(
                sa.update(tenant_audit)
                .where(tenant_audit.c.action_verb == "test.step2")
                .values(after_state={"tampered": True})
            )
            await session.commit()

        result = await adapter.verify_chain(tenant_a_id)
        assert result.is_intact is False
        assert result.break_index == 2
        assert result.length == 5

    event_loop.run_until_complete(run())
