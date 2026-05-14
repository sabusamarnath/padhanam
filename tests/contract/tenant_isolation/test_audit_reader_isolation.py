"""Tenant isolation contract tests for the audit-reader read surface (D24, D32, D35, D102).

Per D32 the per-tenant ``tenant_audit`` table lives on each tenant's
data plane; per D35 the control-plane ``tenant_audit`` table lives
on the dedicated control-plane Postgres instance with the empty-
string ``tenant_id`` sentinel. The S36 read substrate
(``AuditEventReader`` port + ``PostgresAuditEventReader`` adapter)
extends both destinations through one port; this contract harness
verifies tenant isolation holds on the read paths and that the
destination-parameter routing rejects mismatched
``tenant_context`` values at port-method entry.

Four behavioural scenarios per the S36 brief commit 6:

1. Cross-tenant ``get_audit_event`` on per-tenant destination
   returns ``None`` (the event lives on the other tenant's DB).
2. Cross-tenant ``list_audit_events_with_filters`` returns empty
   pages (the filter never matches because the per-tenant DB
   contains no rows from the other tenant).
3. ``get_audit_event`` on per-tenant destination with
   ``tenant_context=None`` raises ``AuditQueryRoutingError`` at
   port-method entry (no SQL issued).
4. ``get_audit_event`` on control-plane destination with a
   populated ``tenant_context`` raises ``AuditQueryRoutingError``
   at port-method entry (no SQL issued).

Synthetic dual-tenant fixture mirrors the run-history contract
harness shape: two synthetic per-tenant databases on the
loopback control-plane Postgres (the S5 host-port-binding
exception); the resolver maps each test tenant_id to its
sessionmaker; cross-tenant reads route to the bound tenant's
database only and surface no rows.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from contexts.audit.adapters.outbound.postgres.audit import tenant_audit
from contexts.audit.adapters.outbound.postgres.reader import (
    PostgresAuditEventReader,
)
from contexts.audit.domain.events import GENESIS_HASH, compute_event_hash
from contexts.audit.domain.query_filters import AuditEventListFilters
from contexts.audit.ports.reader import AuditQueryRoutingError
from padhanam.config import ControlPlaneSettings
from shared_kernel import TenantContext, TenantId


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


def _tc(tenant_id: TenantId) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        cost_attribution_id=str(tenant_id),
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
    """Provision two synthetic per-tenant databases on the loopback
    control-plane Postgres, apply the per-tenant Alembic chain to
    each (creating the tenant_audit table with the
    ``tenant_id <> ''`` CHECK per D35), and yield
    (tenant_a_uuid, tenant_b_uuid, sm_a, sm_b)."""
    settings = _cp_settings()
    suffix = uuid.uuid4().hex[:8]
    tenant_a_db = f"audit_reader_iso_a_{suffix}"
    tenant_b_db = f"audit_reader_iso_b_{suffix}"
    tenant_a_uuid = "00000000-0000-4000-8000-" + suffix.rjust(11, "0") + "a"
    tenant_b_uuid = "00000000-0000-4000-8000-" + suffix.rjust(11, "0") + "b"

    sync_engine = sa.create_engine(_sync_url(settings), isolation_level="AUTOCOMMIT")
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

    tenant_a_engine = create_async_engine(_async_url(settings, tenant_a_db))
    tenant_b_engine = create_async_engine(_async_url(settings, tenant_b_db))
    sm_a = async_sessionmaker(tenant_a_engine, expire_on_commit=False)
    sm_b = async_sessionmaker(tenant_b_engine, expire_on_commit=False)

    try:
        yield (
            TenantId(tenant_a_uuid),
            TenantId(tenant_b_uuid),
            sm_a,
            sm_b,
        )
    finally:
        async def cleanup() -> None:
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


def _build_reader(
    *, sm_a, sm_b, ctx_a, ctx_b
) -> PostgresAuditEventReader:
    sm_by_id = {str(ctx_a): sm_a, str(ctx_b): sm_b}

    async def resolver(tenant_id: TenantId) -> async_sessionmaker[AsyncSession]:
        sm = sm_by_id.get(str(tenant_id))
        if sm is None:
            raise LookupError(f"unexpected tenant_id {tenant_id!r}")
        return sm

    # control-plane sessionmaker is the per-tenant sm_a placeholder
    # because the contract tests do not exercise control-plane reads
    # against real data — scenarios 1/2 are per-tenant cross-tenant;
    # scenarios 3/4 raise pre-routing without ever touching the
    # sessionmaker. The placeholder is structurally typed but is
    # not exercised by any reachable code path in these tests.
    return PostgresAuditEventReader(
        per_tenant_sessionmaker_resolver=resolver,
        control_plane_sessionmaker=sm_a,
    )


def _seed_event(
    event_loop,
    sm,
    *,
    tenant_id: str,
    correlation_id: str,
    timestamp: datetime | None = None,
    actor: str = "user:alice",
) -> uuid.UUID:
    """Seed one valid tenant_audit row via direct SQL insert.

    The row carries a valid hash-chain link computed via
    ``compute_event_hash`` against ``GENESIS_HASH`` so verifications
    pass; tests that need a tampered row construct explicitly.
    """
    ts = timestamp or datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)
    event_id = uuid4()
    resource_id = str(uuid4())
    this_hash = compute_event_hash(
        actor=actor,
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        timestamp=ts.isoformat(),
        action_verb="agent.invoke.end",
        resource_type="agent_run",
        resource_id=resource_id,
        before_state={},
        after_state={"k": "v"},
        correlation_id=correlation_id,
        previous_event_hash=GENESIS_HASH,
    )

    async def insert() -> None:
        async with sm() as session:
            async with session.begin():
                await session.execute(
                    sa.insert(tenant_audit).values(
                        id=str(event_id),
                        tenant_id=tenant_id,
                        actor=actor,
                        jurisdiction="eu-west",
                        timestamp=ts,
                        action_verb="agent.invoke.end",
                        resource_type="agent_run",
                        resource_id=resource_id,
                        before_state={},
                        after_state={"k": "v"},
                        correlation_id=correlation_id,
                        previous_event_hash=GENESIS_HASH,
                        this_event_hash=this_hash,
                    )
                )

    event_loop.run_until_complete(insert())
    return event_id


# --------------------------------------------------------------------
# Scenario 1: cross-tenant get_audit_event returns None.
# --------------------------------------------------------------------


def test_get_audit_event_returns_none_for_event_on_other_tenant(
    event_loop, isolation_setup
) -> None:
    """An event_id present on tenant_b is invisible to a per-tenant
    read scoped to tenant_a. Cross-tenant read isolation at the
    row-id level."""
    ctx_a, ctx_b, sm_a, sm_b = isolation_setup

    # Seed an event on tenant_b.
    event_id_on_b = _seed_event(
        event_loop, sm_b, tenant_id=str(ctx_b), correlation_id="corr-b"
    )

    reader = _build_reader(sm_a=sm_a, sm_b=sm_b, ctx_a=ctx_a, ctx_b=ctx_b)

    async def call() -> Any:
        return await reader.get_audit_event(
            destination="per_tenant",
            event_id=event_id_on_b,
            tenant_context=_tc(ctx_a),  # tenant_a-scoped read
        )

    result = event_loop.run_until_complete(call())
    assert result is None


# --------------------------------------------------------------------
# Scenario 2: cross-tenant list_audit_events_with_filters empty.
# --------------------------------------------------------------------


def test_list_audit_events_returns_empty_page_for_other_tenant_data(
    event_loop, isolation_setup
) -> None:
    """A filter that would match an event on tenant_b returns an
    empty page when queried through a tenant_a-scoped read.
    Cross-tenant read isolation at the filter level."""
    ctx_a, ctx_b, sm_a, sm_b = isolation_setup

    # Seed an event on tenant_b with a known correlation_id.
    target_correlation_id = "corr-cross-tenant-target"
    _seed_event(
        event_loop,
        sm_b,
        tenant_id=str(ctx_b),
        correlation_id=target_correlation_id,
    )

    reader = _build_reader(sm_a=sm_a, sm_b=sm_b, ctx_a=ctx_a, ctx_b=ctx_b)

    async def call() -> Any:
        return await reader.list_audit_events_with_filters(
            destination="per_tenant",
            filters=AuditEventListFilters(
                correlation_id=target_correlation_id
            ),
            cursor=None,
            page_size=10,
            tenant_context=_tc(ctx_a),  # tenant_a-scoped read
        )

    page = event_loop.run_until_complete(call())
    assert page.events == ()
    assert page.next_cursor is None


def test_list_audit_events_tenant_a_sees_only_tenant_a_rows(
    event_loop, isolation_setup
) -> None:
    """Positive case complement of the scenario above: a tenant_a
    read with no filters returns exactly the rows seeded on
    tenant_a, none of the ones seeded on tenant_b."""
    ctx_a, ctx_b, sm_a, sm_b = isolation_setup

    # Seed one row on each tenant.
    event_id_on_a = _seed_event(
        event_loop, sm_a, tenant_id=str(ctx_a), correlation_id="corr-a"
    )
    _seed_event(
        event_loop, sm_b, tenant_id=str(ctx_b), correlation_id="corr-b"
    )

    reader = _build_reader(sm_a=sm_a, sm_b=sm_b, ctx_a=ctx_a, ctx_b=ctx_b)

    async def call() -> Any:
        return await reader.list_audit_events_with_filters(
            destination="per_tenant",
            filters=AuditEventListFilters(),
            cursor=None,
            page_size=10,
            tenant_context=_tc(ctx_a),
        )

    page = event_loop.run_until_complete(call())
    # Exactly one event returned, and it's tenant_a's.
    assert len(page.events) == 1
    assert page.events[0].id == event_id_on_a
    assert page.events[0].tenant_id == str(ctx_a)


# --------------------------------------------------------------------
# Scenario 3: per_tenant without tenant_context raises pre-routing.
# --------------------------------------------------------------------


def test_get_per_tenant_without_tenant_context_raises_pre_routing(
    event_loop, isolation_setup
) -> None:
    """``destination='per_tenant'`` with ``tenant_context=None``
    raises ``AuditQueryRoutingError`` at port-method entry; no SQL
    issued, no session opened. The defence ensures a caller bug
    cannot accidentally read with no tenant scope."""
    ctx_a, ctx_b, sm_a, sm_b = isolation_setup
    # Seed one row so a missing scope would otherwise return it.
    _seed_event(
        event_loop, sm_a, tenant_id=str(ctx_a), correlation_id="corr-a"
    )

    reader = _build_reader(sm_a=sm_a, sm_b=sm_b, ctx_a=ctx_a, ctx_b=ctx_b)

    async def call() -> None:
        await reader.get_audit_event(
            destination="per_tenant",
            event_id=uuid4(),
            tenant_context=None,
        )

    with pytest.raises(AuditQueryRoutingError, match="per_tenant"):
        event_loop.run_until_complete(call())


# --------------------------------------------------------------------
# Scenario 4: control_plane with tenant_context raises pre-routing.
# --------------------------------------------------------------------


def test_get_control_plane_with_tenant_context_raises_pre_routing(
    event_loop, isolation_setup
) -> None:
    """``destination='control_plane'`` with a populated
    ``tenant_context`` raises ``AuditQueryRoutingError`` at port-
    method entry. The defence ensures a caller bug cannot
    accidentally read control-plane events through a tenant-scoped
    intent (the tenant_context would be silently ignored
    otherwise, which is a security smell)."""
    ctx_a, ctx_b, sm_a, sm_b = isolation_setup

    reader = _build_reader(sm_a=sm_a, sm_b=sm_b, ctx_a=ctx_a, ctx_b=ctx_b)

    async def call() -> None:
        await reader.get_audit_event(
            destination="control_plane",
            event_id=uuid4(),
            tenant_context=_tc(ctx_a),
        )

    with pytest.raises(AuditQueryRoutingError, match="control_plane"):
        event_loop.run_until_complete(call())


def test_list_control_plane_with_tenant_context_raises_pre_routing(
    event_loop, isolation_setup
) -> None:
    """Same defence on ``list_audit_events_with_filters``: routing
    error surfaces before any SQL touches the control-plane
    sessionmaker."""
    ctx_a, ctx_b, sm_a, sm_b = isolation_setup

    reader = _build_reader(sm_a=sm_a, sm_b=sm_b, ctx_a=ctx_a, ctx_b=ctx_b)

    async def call() -> None:
        await reader.list_audit_events_with_filters(
            destination="control_plane",
            filters=AuditEventListFilters(),
            cursor=None,
            page_size=10,
            tenant_context=_tc(ctx_a),
        )

    with pytest.raises(AuditQueryRoutingError, match="control_plane"):
        event_loop.run_until_complete(call())


def test_list_per_tenant_without_tenant_context_raises_pre_routing(
    event_loop, isolation_setup
) -> None:
    """Same defence on ``list_audit_events_with_filters`` for the
    per-tenant direction. Defence-in-depth in both directions on
    both methods."""
    ctx_a, ctx_b, sm_a, sm_b = isolation_setup

    reader = _build_reader(sm_a=sm_a, sm_b=sm_b, ctx_a=ctx_a, ctx_b=ctx_b)

    async def call() -> None:
        await reader.list_audit_events_with_filters(
            destination="per_tenant",
            filters=AuditEventListFilters(),
            cursor=None,
            page_size=10,
            tenant_context=None,
        )

    with pytest.raises(AuditQueryRoutingError, match="per_tenant"):
        event_loop.run_until_complete(call())
