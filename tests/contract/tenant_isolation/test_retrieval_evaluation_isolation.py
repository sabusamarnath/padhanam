"""Tenant isolation contract tests for the retrieval_evaluation context (D24, D32, D109).

Per D32, per-tenant data planes are independent Postgres instances.
Per D109, the three retrieval-evaluation tables (``gold_sets``,
``gold_set_revisions``, ``gold_set_entries``) live on each tenant's
database, NOT on the control plane.

Two layers, mirroring test_run_history_isolation.py and
test_audit_isolation.py:

1. Structural isolation: each tenant's DB carries the three tables;
   the control-plane DB does not.

2. Behavioural cross-tenant isolation: a tenant-A gold set persisted
   via ``PostgresGoldSetRepository`` lands on tenant_a's DB only;
   tenant_b's DB stays empty. Cross-tenant reads return None
   because the adapter routes to the bound tenant's DB. The
   defence-in-depth ValueError on a tenant_id mismatch is exercised
   for persist_new_gold_set.

Synthetic dual-tenant fixture provisions two databases on the
loopback control-plane Postgres (S5 host-port-binding exception);
the resolver maps each test tenant_id to its sessionmaker;
cross-tenant writes route to the bound tenant's database only.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from contexts.retrieval_evaluation.adapters.outbound.postgres._tables import (
    gold_set_entries,
    gold_set_revisions,
    gold_sets,
)
from contexts.retrieval_evaluation.adapters.outbound.postgres.reader import (
    PostgresGoldSetReader,
)
from contexts.retrieval_evaluation.adapters.outbound.postgres.repository import (
    PostgresGoldSetRepository,
)
from contexts.retrieval_evaluation.domain import (
    GoldSet,
    GoldSetEntry,
    GoldSetRevision,
    GoldSetRevisionStatus,
)
from padhanam.config import ControlPlaneSettings
from shared_kernel import TenantContext, TenantId


_RETRIEVAL_EVALUATION_TABLES = (
    "gold_set_entries",
    "gold_set_revisions",
    "gold_sets",
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
    in_clause = ", ".join(f"'{t}'" for t in _RETRIEVAL_EVALUATION_TABLES)
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
def test_per_tenant_db_has_all_three_retrieval_evaluation_tables(
    compose_running: None,
    service: str,
    user_env: str,
    db_env: str,
) -> None:
    """D32 / D109: each tenant's DB carries the three substrate tables."""
    user = _env(user_env)
    db = _env(db_env)
    found = set(
        _exec_psql(service, user, db, _table_list_query()).splitlines()
    )
    assert found == set(_RETRIEVAL_EVALUATION_TABLES), (
        f"per-tenant DB {service} missing retrieval-evaluation tables; "
        f"found {sorted(found)}"
    )


def test_control_plane_db_has_no_retrieval_evaluation_tables(
    compose_running: None,
) -> None:
    """D32 / D109: control-plane has no retrieval-evaluation tables.
    Gold sets are tenant-authored audit evidence; control-plane
    storage would violate D32's tenant data plane separation."""
    user = _env("POSTGRES_CONTROL_PLANE_USER")
    db = _env("POSTGRES_CONTROL_PLANE_DB")
    found = _exec_psql(
        "postgres-control-plane", user, db, _table_list_query()
    )
    assert found == "", (
        f"control-plane should have no retrieval-evaluation tables; "
        f"psql reported {found!r}"
    )


def test_gold_sets_deferred_fk_per_tenant(
    compose_running: None,
) -> None:
    """gold_sets.current_revision_id FK is DEFERRABLE INITIALLY DEFERRED
    per D109. The create-gold-set use case relies on the deferred check
    to insert aggregate + initial draft revision in one transaction."""
    for service, user_env, db_env in [
        ("postgres-tenant-a", "POSTGRES_TENANT_A_USER", "POSTGRES_TENANT_A_DB"),
        ("postgres-tenant-b", "POSTGRES_TENANT_B_USER", "POSTGRES_TENANT_B_DB"),
    ]:
        user = _env(user_env)
        db = _env(db_env)
        query = (
            "SELECT condeferrable, condeferred FROM pg_constraint "
            "WHERE conname = 'gold_sets_current_revision_id_fkey'"
        )
        found = _exec_psql(service, user, db, query)
        # pg_constraint returns 't|t' for deferrable + deferred
        assert found == "t|t", (
            f"{service} gold_sets_current_revision_id_fkey is not "
            f"DEFERRABLE INITIALLY DEFERRED (pg_constraint={found!r}); "
            "the deferred FK is required by the create_gold_set use case"
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


def _make_gold_set(
    *,
    tenant_id: uuid.UUID,
    gold_set_id: uuid.UUID | None = None,
) -> GoldSet:
    return GoldSet(
        id=gold_set_id or uuid4(),
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        name=f"isolation-test-{uuid4().hex[:8]}",
        created_by_user_id="iso-test",
        created_at=datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc),
        current_revision_id=None,
    )


def _make_initial_revision(
    *, gold_set_id: uuid.UUID
) -> GoldSetRevision:
    return GoldSetRevision(
        id=uuid4(),
        gold_set_id=gold_set_id,
        revision_number=1,
        status=GoldSetRevisionStatus.DRAFT,
        created_by_user_id="iso-test",
        created_at=datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc),
        finalized_at=None,
        this_event_hash=None,
        previous_event_hash=None,
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
    tenant_a_db = f"gold_set_iso_a_{suffix}"
    tenant_b_db = f"gold_set_iso_b_{suffix}"
    tenant_a_uuid = uuid.UUID(
        "00000000-0000-4000-8000-" + suffix.rjust(11, "0") + "a"
    )
    tenant_b_uuid = uuid.UUID(
        "00000000-0000-4000-8000-" + suffix.rjust(11, "0") + "b"
    )

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

    tenant_a_engine = create_async_engine(_async_url(settings, tenant_a_db))
    tenant_b_engine = create_async_engine(_async_url(settings, tenant_b_db))
    sm_a = async_sessionmaker(tenant_a_engine, expire_on_commit=False)
    sm_b = async_sessionmaker(tenant_b_engine, expire_on_commit=False)

    try:
        yield (tenant_a_uuid, tenant_b_uuid, sm_a, sm_b)
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


def _row_count(event_loop, sm, table) -> int:
    async def run() -> int:
        async with sm() as session:
            return (
                await session.execute(
                    sa.select(sa.func.count()).select_from(table)
                )
            ).scalar() or 0
    return event_loop.run_until_complete(run())


def _build_repo(
    *, bound_tenant_id: uuid.UUID, sm
) -> PostgresGoldSetRepository:
    async def resolver(_tid: TenantId):
        return sm

    return PostgresGoldSetRepository(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=TenantId(str(bound_tenant_id)),
    )


def _build_reader(
    *, bound_tenant_id: uuid.UUID, sm
) -> PostgresGoldSetReader:
    async def resolver(_tid: TenantId):
        return sm

    return PostgresGoldSetReader(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=TenantId(str(bound_tenant_id)),
    )


def _tenant_context(tenant_id: uuid.UUID) -> TenantContext:
    return TenantContext(
        tenant_id=str(tenant_id),
        jurisdiction="eu-west",
        cost_attribution_id=str(tenant_id),
    )


def test_persist_new_gold_set_isolated_per_tenant(
    event_loop, isolation_setup
) -> None:
    """Cross-tenant write isolation: a tenant-A persist lands on
    tenant_a's DB only; tenant_b's gold_sets table remains empty."""
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    repo = _build_repo(bound_tenant_id=tenant_a, sm=sm_a)
    gold_set = _make_gold_set(tenant_id=tenant_a)
    initial = _make_initial_revision(gold_set_id=gold_set.id)

    event_loop.run_until_complete(
        repo.persist_new_gold_set(
            tenant_context=_tenant_context(tenant_a),
            gold_set=gold_set,
            initial_revision=initial,
        )
    )

    assert _row_count(event_loop, sm_a, gold_sets) == 1
    assert _row_count(event_loop, sm_a, gold_set_revisions) == 1
    assert _row_count(event_loop, sm_b, gold_sets) == 0
    assert _row_count(event_loop, sm_b, gold_set_revisions) == 0


def test_persist_with_b_tenant_id_routes_to_b_database(
    event_loop, isolation_setup
) -> None:
    """Reverse direction symmetry."""
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    repo = _build_repo(bound_tenant_id=tenant_b, sm=sm_b)
    gold_set = _make_gold_set(tenant_id=tenant_b)
    initial = _make_initial_revision(gold_set_id=gold_set.id)

    event_loop.run_until_complete(
        repo.persist_new_gold_set(
            tenant_context=_tenant_context(tenant_b),
            gold_set=gold_set,
            initial_revision=initial,
        )
    )

    assert _row_count(event_loop, sm_b, gold_sets) == 1
    assert _row_count(event_loop, sm_a, gold_sets) == 0


def test_adapter_rejects_tenant_context_mismatch_pre_routing(
    event_loop, isolation_setup
) -> None:
    """Defence-in-depth per D24 / D32: a call with a TenantContext
    whose tenant_id doesn't match the adapter's bound tenant raises
    ValueError before any session resolution."""
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    repo_for_a = _build_repo(bound_tenant_id=tenant_a, sm=sm_a)
    gold_set = _make_gold_set(tenant_id=tenant_b)
    initial = _make_initial_revision(gold_set_id=gold_set.id)

    with pytest.raises(ValueError, match="tenant"):
        event_loop.run_until_complete(
            repo_for_a.persist_new_gold_set(
                tenant_context=_tenant_context(tenant_b),
                gold_set=gold_set,
                initial_revision=initial,
            )
        )

    assert _row_count(event_loop, sm_a, gold_sets) == 0
    assert _row_count(event_loop, sm_b, gold_sets) == 0


def test_adapter_rejects_gold_set_tenant_mismatch(
    event_loop, isolation_setup
) -> None:
    """Second defence-in-depth check: even if TenantContext matches,
    a GoldSet aggregate whose tenant_id differs from the bound tenant
    is rejected. Guards against assembly bugs where the aggregate is
    built with one tenant and routed under another's context."""
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    repo_for_a = _build_repo(bound_tenant_id=tenant_a, sm=sm_a)
    gold_set = _make_gold_set(tenant_id=tenant_b)
    initial = _make_initial_revision(gold_set_id=gold_set.id)

    with pytest.raises(ValueError, match="tenant"):
        event_loop.run_until_complete(
            repo_for_a.persist_new_gold_set(
                tenant_context=_tenant_context(tenant_a),
                gold_set=gold_set,
                initial_revision=initial,
            )
        )

    assert _row_count(event_loop, sm_a, gold_sets) == 0


def test_cross_tenant_get_returns_none(
    event_loop, isolation_setup
) -> None:
    """A gold set persisted to tenant_a returns None when read
    through a reader bound to tenant_b — the adapter routes to
    tenant_b's DB where the row does not exist."""
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    repo_a = _build_repo(bound_tenant_id=tenant_a, sm=sm_a)
    gold_set = _make_gold_set(tenant_id=tenant_a)
    initial = _make_initial_revision(gold_set_id=gold_set.id)
    event_loop.run_until_complete(
        repo_a.persist_new_gold_set(
            tenant_context=_tenant_context(tenant_a),
            gold_set=gold_set,
            initial_revision=initial,
        )
    )

    reader_b = _build_reader(bound_tenant_id=tenant_b, sm=sm_b)
    result = event_loop.run_until_complete(
        reader_b.get_gold_set_with_current_revision(
            tenant_context=_tenant_context(tenant_b),
            gold_set_id=gold_set.id,
        )
    )
    assert result is None


def test_cross_tenant_list_returns_empty(
    event_loop, isolation_setup
) -> None:
    """Tenant-B's list view never includes tenant-A's gold sets."""
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    repo_a = _build_repo(bound_tenant_id=tenant_a, sm=sm_a)
    gold_set = _make_gold_set(tenant_id=tenant_a)
    initial = _make_initial_revision(gold_set_id=gold_set.id)
    event_loop.run_until_complete(
        repo_a.persist_new_gold_set(
            tenant_context=_tenant_context(tenant_a),
            gold_set=gold_set,
            initial_revision=initial,
        )
    )

    reader_b = _build_reader(bound_tenant_id=tenant_b, sm=sm_b)
    page = event_loop.run_until_complete(
        reader_b.list_gold_sets(
            tenant_context=_tenant_context(tenant_b),
            cursor=None,
            page_size=10,
        )
    )
    assert page.gold_sets == ()
    assert page.next_cursor is None


def test_cross_tenant_find_draft_returns_none(
    event_loop, isolation_setup
) -> None:
    """The find_current_draft_revision read returns None across
    tenant boundaries."""
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    repo_a = _build_repo(bound_tenant_id=tenant_a, sm=sm_a)
    gold_set = _make_gold_set(tenant_id=tenant_a)
    initial = _make_initial_revision(gold_set_id=gold_set.id)
    event_loop.run_until_complete(
        repo_a.persist_new_gold_set(
            tenant_context=_tenant_context(tenant_a),
            gold_set=gold_set,
            initial_revision=initial,
        )
    )

    reader_b = _build_reader(bound_tenant_id=tenant_b, sm=sm_b)
    result = event_loop.run_until_complete(
        reader_b.find_current_draft_revision(
            tenant_context=_tenant_context(tenant_b),
            gold_set_id=gold_set.id,
        )
    )
    assert result is None


def test_cross_tenant_get_revision_returns_none(
    event_loop, isolation_setup
) -> None:
    """get_revision_with_entries returns None when the revision's
    parent gold set belongs to a different tenant than the reader
    is bound to. Defence-in-depth at the JOIN through gold_sets."""
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    repo_a = _build_repo(bound_tenant_id=tenant_a, sm=sm_a)
    gold_set = _make_gold_set(tenant_id=tenant_a)
    initial = _make_initial_revision(gold_set_id=gold_set.id)
    event_loop.run_until_complete(
        repo_a.persist_new_gold_set(
            tenant_context=_tenant_context(tenant_a),
            gold_set=gold_set,
            initial_revision=initial,
        )
    )

    reader_b = _build_reader(bound_tenant_id=tenant_b, sm=sm_b)
    result = event_loop.run_until_complete(
        reader_b.get_revision_with_entries(
            tenant_context=_tenant_context(tenant_b),
            revision_id=initial.id,
        )
    )
    assert result is None


def test_cross_tenant_append_entry_to_isolated_revision_fails(
    event_loop, isolation_setup
) -> None:
    """append_entry against tenant_a's revision via a tenant_b-bound
    adapter fails because the revision id does not exist on tenant_b's
    DB. The adapter's status-check raises before any insert lands."""
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    repo_a = _build_repo(bound_tenant_id=tenant_a, sm=sm_a)
    gold_set = _make_gold_set(tenant_id=tenant_a)
    initial = _make_initial_revision(gold_set_id=gold_set.id)
    event_loop.run_until_complete(
        repo_a.persist_new_gold_set(
            tenant_context=_tenant_context(tenant_a),
            gold_set=gold_set,
            initial_revision=initial,
        )
    )

    repo_b = _build_repo(bound_tenant_id=tenant_b, sm=sm_b)
    entry = GoldSetEntry(
        id=uuid4(),
        gold_set_revision_id=initial.id,
        entry_index=0,
        query="x",
        expected_chunk_ids=(uuid4(),),
    )
    with pytest.raises(ValueError):
        event_loop.run_until_complete(
            repo_b.append_entry(
                tenant_context=_tenant_context(tenant_b),
                entry=entry,
            )
        )

    assert _row_count(event_loop, sm_a, gold_set_entries) == 0
    assert _row_count(event_loop, sm_b, gold_set_entries) == 0
