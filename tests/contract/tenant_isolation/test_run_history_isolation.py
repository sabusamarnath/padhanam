"""Tenant isolation contract tests for the run-history context (D24, D32, D95).

Per D32, per-tenant data planes are independent Postgres instances.
Per D95, the run-history context is per-tenant-scoped: the three
new tables (``runs``, ``run_chunk_citations``,
``run_entity_citations``) live on each tenant's database, NOT on
the control plane.

Two layers, mirroring test_audit_isolation.py and
test_agent_isolation.py:

1. Structural isolation (information_schema query): each tenant's
   DB carries the three run-history tables; the control-plane DB
   does not. Asserted by shelling out to docker compose exec.

2. Behavioural cross-tenant isolation: a tenant-A RunRecord
   persisted via ``PostgresRunHistoryAdapter`` lands on tenant_a's
   DB only; tenant_b's DB remains empty for that record. The
   adapter's defence-in-depth (bound_tenant_id mismatch ValueError
   per D24 / D32) is also exercised.

Synthetic dual-tenant fixture provisions two databases on the
loopback control-plane Postgres (the S5 host-port-binding
exception); the resolver maps each test tenant_id to its
sessionmaker; cross-tenant writes route to the bound tenant's
database only.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from contexts.run_history.adapters.outbound.postgres import (
    PostgresRunHistoryAdapter,
    runs,
)
from contexts.run_history.domain.run_record import RunRecord
from padhanam.config import ControlPlaneSettings
from shared_kernel import TenantId


_RUN_HISTORY_TABLES = (
    "run_chunk_citations",
    "run_entity_citations",
    "runs",
)


# --------------------------------------------------------------------
# Layer 1: structural isolation (information_schema query).
# --------------------------------------------------------------------


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        subprocess.run(
            ["docker", "compose", "ps", "-q"],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return False
    return True


def _exec_psql(service: str, user: str, db: str, query: str) -> str:
    cmd = [
        "docker", "compose", "exec", "-T", service,
        "psql", "-U", user, "-d", db, "-tAc", query,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        raise RuntimeError(
            f"psql failed in {service}: stderr={result.stderr!r}"
        )
    return result.stdout.strip()


@pytest.fixture(scope="module")
def compose_running() -> None:
    if not _docker_available():
        pytest.skip("docker compose not reachable")
    services = subprocess.run(
        ["docker", "compose", "ps", "--services", "--filter", "status=running"],
        capture_output=True, text=True, check=False,
    )
    running = set(services.stdout.split())
    needed = {"postgres-control-plane", "postgres-tenant-a", "postgres-tenant-b"}
    if not needed.issubset(running):
        pytest.skip(f"compose services not running: {sorted(needed - running)}")


def _env(key: str) -> str:
    value = os.environ.get(key)
    if value:
        return value
    try:
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1]
    except FileNotFoundError:
        pass
    raise RuntimeError(f"env var {key} not set and not in .env")


def _table_list_query() -> str:
    in_clause = ", ".join(f"'{t}'" for t in _RUN_HISTORY_TABLES)
    return (
        "SELECT table_name FROM information_schema.tables "
        f"WHERE table_schema='public' AND table_name IN ({in_clause}) "
        "ORDER BY table_name"
    )


@pytest.mark.parametrize(
    "service,user_env,db_env",
    [
        ("postgres-tenant-a", "POSTGRES_TENANT_A_USER", "POSTGRES_TENANT_A_DB"),
        ("postgres-tenant-b", "POSTGRES_TENANT_B_USER", "POSTGRES_TENANT_B_DB"),
    ],
)
def test_per_tenant_db_has_all_three_run_history_tables(
    compose_running: None,
    service: str,
    user_env: str,
    db_env: str,
) -> None:
    """D32 / D95 positive case: each tenant's DB has all three
    run-history tables."""
    user = _env(user_env)
    db = _env(db_env)
    found = set(_exec_psql(service, user, db, _table_list_query()).splitlines())
    assert found == set(_RUN_HISTORY_TABLES), (
        f"per-tenant DB {service} missing run-history tables; "
        f"found {sorted(found)}"
    )


def test_control_plane_db_has_no_run_history_tables(
    compose_running: None,
) -> None:
    """D32 / D95 negative case: control-plane DB has no run-history
    tables. Run history is per-tenant audit evidence; control-plane
    storage would violate D32's tenant data plane separation."""
    user = _env("POSTGRES_CONTROL_PLANE_USER")
    db = _env("POSTGRES_CONTROL_PLANE_DB")
    found = _exec_psql(
        "postgres-control-plane", user, db, _table_list_query()
    )
    assert found == "", (
        f"control-plane should have no run-history tables; "
        f"psql reported {found!r}"
    )


def test_run_chunk_citations_table_exists_per_tenant(
    compose_running: None,
) -> None:
    """Both tenants have run_chunk_citations table with the chunks
    FK ON DELETE SET NULL behavior per D95."""
    for service, user_env, db_env in [
        ("postgres-tenant-a", "POSTGRES_TENANT_A_USER", "POSTGRES_TENANT_A_DB"),
        ("postgres-tenant-b", "POSTGRES_TENANT_B_USER", "POSTGRES_TENANT_B_DB"),
    ]:
        user = _env(user_env)
        db = _env(db_env)
        query = (
            "SELECT confdeltype FROM pg_constraint "
            "WHERE conname = 'run_chunk_citations_chunk_id_fkey'"
        )
        found = _exec_psql(service, user, db, query)
        # PG confdeltype = 'n' for SET NULL per pg_catalog
        assert found == "n", (
            f"{service} run_chunk_citations.chunk_id FK is not ON DELETE "
            f"SET NULL (confdeltype={found!r}); D95 audit-evidence "
            "snapshot survival commitment requires SET NULL"
        )


def test_run_entity_citations_table_exists_per_tenant(
    compose_running: None,
) -> None:
    """Both tenants have run_entity_citations table per D95."""
    for service, user_env, db_env in [
        ("postgres-tenant-a", "POSTGRES_TENANT_A_USER", "POSTGRES_TENANT_A_DB"),
        ("postgres-tenant-b", "POSTGRES_TENANT_B_USER", "POSTGRES_TENANT_B_DB"),
    ]:
        user = _env(user_env)
        db = _env(db_env)
        query = (
            "SELECT conname FROM pg_constraint "
            "WHERE conname = 'run_entity_citations_run_id_fkey'"
        )
        found = _exec_psql(service, user, db, query)
        assert found == "run_entity_citations_run_id_fkey", (
            f"{service} missing run_entity_citations_run_id_fkey FK"
        )


# --------------------------------------------------------------------
# Layer 2: behavioural cross-tenant isolation (synthetic DB pattern).
# --------------------------------------------------------------------


CONTROL_PLANE_HOST = os.environ.get("CONTROL_PLANE_HOST_OVERRIDE", "127.0.0.1")
CONTROL_PLANE_PORT = int(os.environ.get("CONTROL_PLANE_PORT_OVERRIDE", "5433"))


def _cp_settings() -> ControlPlaneSettings:
    base = ControlPlaneSettings()
    return ControlPlaneSettings(
        user=base.user, password=base.password, db=base.db,
        host=CONTROL_PLANE_HOST, port=CONTROL_PLANE_PORT,
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


def _make_record(*, tenant_id: str, run_id: uuid.UUID | None = None) -> RunRecord:
    return RunRecord(
        id=run_id or uuid4(),
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        agent_template_id=uuid4(),
        agent_template_version=1,
        input_message="isolation test",
        output_content="ok",
        started_at=datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 5, 13, 12, 1, 0, tzinfo=timezone.utc),
        termination_reason="content",
        iteration_count=1,
        total_cost_usd=Decimal("0.001"),
        trace_id=None,
        audit_start_hash="0" * 64,
        audit_end_hash="1" * 64,
        created_at=datetime(2026, 5, 13, 12, 1, 5, tzinfo=timezone.utc),
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
    each, and yield (tenant_a_uuid, tenant_b_uuid, sm_a, sm_b)."""
    settings = _cp_settings()
    suffix = uuid.uuid4().hex[:8]
    tenant_a_db = f"run_history_iso_a_{suffix}"
    tenant_b_db = f"run_history_iso_b_{suffix}"
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


def _row_count(event_loop, sm) -> int:
    async def run() -> int:
        async with sm() as session:
            return (
                await session.execute(
                    sa.select(sa.func.count()).select_from(runs)
                )
            ).scalar() or 0
    return event_loop.run_until_complete(run())


def _build_adapter(
    *, bound_tenant_id: TenantId, sm_a, sm_b, ctx_a, ctx_b
) -> PostgresRunHistoryAdapter:
    sm_by_id = {str(ctx_a): sm_a, str(ctx_b): sm_b}

    async def resolver(tenant_id: TenantId):
        sm = sm_by_id.get(str(tenant_id))
        if sm is None:
            raise LookupError(f"unexpected tenant_id {tenant_id!r}")
        return sm

    return PostgresRunHistoryAdapter(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=bound_tenant_id,
    )


def test_record_run_isolated_per_tenant(
    event_loop, isolation_setup
) -> None:
    """Cross-tenant write isolation: a tenant-A persist lands on
    tenant_a's DB only; tenant_b's runs table remains empty."""
    ctx_a, ctx_b, sm_a, sm_b = isolation_setup
    adapter = _build_adapter(
        bound_tenant_id=ctx_a, sm_a=sm_a, sm_b=sm_b, ctx_a=ctx_a, ctx_b=ctx_b
    )

    record = _make_record(tenant_id=str(ctx_a))
    event_loop.run_until_complete(adapter.persist(record))

    assert _row_count(event_loop, sm_a) == 1
    assert _row_count(event_loop, sm_b) == 0


def test_record_run_with_b_tenant_id_routes_to_b_database(
    event_loop, isolation_setup
) -> None:
    """Reverse direction: a tenant-B persist via a tenant-B-bound
    adapter lands on tenant_b's DB only; tenant_a's runs table
    stays empty. Verifies the tenant_id-to-database routing layer
    holds symmetrically."""
    ctx_a, ctx_b, sm_a, sm_b = isolation_setup
    adapter = _build_adapter(
        bound_tenant_id=ctx_b, sm_a=sm_a, sm_b=sm_b, ctx_a=ctx_a, ctx_b=ctx_b
    )

    record = _make_record(tenant_id=str(ctx_b))
    event_loop.run_until_complete(adapter.persist(record))

    assert _row_count(event_loop, sm_b) == 1
    assert _row_count(event_loop, sm_a) == 0


def test_runs_query_returns_empty_for_unwritten_tenant(
    event_loop, isolation_setup
) -> None:
    """Cross-tenant read isolation: tenant-A writes a record; a
    query for that record's id against tenant_b's runs table
    returns empty (the row does not exist on tenant_b's DB)."""
    ctx_a, ctx_b, sm_a, sm_b = isolation_setup
    adapter = _build_adapter(
        bound_tenant_id=ctx_a, sm_a=sm_a, sm_b=sm_b, ctx_a=ctx_a, ctx_b=ctx_b
    )

    record = _make_record(tenant_id=str(ctx_a))
    event_loop.run_until_complete(adapter.persist(record))

    async def query_for_id_on_b() -> int:
        async with sm_b() as session:
            return (
                await session.execute(
                    sa.select(sa.func.count())
                    .select_from(runs)
                    .where(runs.c.id == str(record.id))
                )
            ).scalar() or 0

    assert event_loop.run_until_complete(query_for_id_on_b()) == 0


def test_adapter_rejects_tenant_id_mismatch_pre_routing(
    event_loop, isolation_setup
) -> None:
    """Defence-in-depth per D24 / D32: a RunRecord whose tenant_id
    doesn't match the adapter's bound tenant raises ValueError
    before any session resolution. This guards against bugs where
    a record might be assembled with one tenant_id but submitted
    to an adapter bound to another."""
    ctx_a, ctx_b, sm_a, sm_b = isolation_setup
    adapter_for_a = _build_adapter(
        bound_tenant_id=ctx_a, sm_a=sm_a, sm_b=sm_b, ctx_a=ctx_a, ctx_b=ctx_b
    )

    foreign_record = _make_record(tenant_id=str(ctx_b))
    with pytest.raises(ValueError, match="tenant"):
        event_loop.run_until_complete(adapter_for_a.persist(foreign_record))

    assert _row_count(event_loop, sm_a) == 0
    assert _row_count(event_loop, sm_b) == 0
