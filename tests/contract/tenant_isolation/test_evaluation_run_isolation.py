"""Tenant isolation contract tests for the retrieval-evaluation runner (D24, D32, D110).

Per D32, per-tenant data planes are independent Postgres instances.
Per D110, the three runner-substrate tables (``evaluation_runs``,
``evaluation_results``, ``evaluation_aggregates``) live on each
tenant's database, NOT on the control plane.

Two layers, mirroring ``test_retrieval_evaluation_isolation.py``:

1. Structural isolation: each tenant's DB carries the three new tables
   from migration 0014; the control-plane DB does not.

2. Behavioural cross-tenant isolation: a tenant-A run persisted via
   ``PostgresEvaluationRunRepository`` lands on tenant_a's DB only;
   tenant_b's DB stays empty. Cross-tenant reads return None. The
   defence-in-depth ValueError fires on TenantContext or
   EvaluationRun.tenant_id mismatch. The terminal-state transition
   refuses to fire when the run is not owned by the bound tenant.
   FK from ``evaluation_runs`` to ``gold_sets`` / ``gold_set_revisions``
   on the same DB makes cross-tenant run-to-gold-set association
   structurally impossible (each tenant's DB only contains its own
   gold sets).

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
from decimal import Decimal
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
    evaluation_aggregates,
    evaluation_results,
    evaluation_runs,
)
from contexts.retrieval_evaluation.adapters.outbound.postgres.evaluation_run_reader import (
    PostgresEvaluationRunReader,
)
from contexts.retrieval_evaluation.adapters.outbound.postgres.evaluation_run_repository import (
    PostgresEvaluationRunRepository,
)
from contexts.retrieval_evaluation.adapters.outbound.postgres.repository import (
    PostgresGoldSetRepository,
)
from contexts.retrieval_evaluation.domain import (
    EvaluationAggregate,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunStatus,
    GoldSet,
    GoldSetEntry,
    GoldSetRevision,
    GoldSetRevisionStatus,
)
from padhanam.config import ControlPlaneSettings
from shared_kernel import TenantContext, TenantId


_RUNNER_TABLES = (
    "evaluation_aggregates",
    "evaluation_results",
    "evaluation_runs",
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
    in_clause = ", ".join(f"'{t}'" for t in _RUNNER_TABLES)
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
def test_per_tenant_db_has_all_three_evaluation_runner_tables(
    compose_running: None,
    service: str,
    user_env: str,
    db_env: str,
) -> None:
    """D32 / D110: each tenant's DB carries the three runner-substrate tables."""
    user = _env(user_env)
    db = _env(db_env)
    found = set(
        _exec_psql(service, user, db, _table_list_query()).splitlines()
    )
    assert found == set(_RUNNER_TABLES), (
        f"per-tenant DB {service} missing runner-substrate tables; "
        f"found {sorted(found)}"
    )


def test_control_plane_db_has_no_evaluation_runner_tables(
    compose_running: None,
) -> None:
    """D32 / D110: control-plane has no runner-substrate tables. Runner
    records are platform-computed against per-tenant gold sets;
    control-plane storage would violate D32."""
    user = _env("POSTGRES_CONTROL_PLANE_USER")
    db = _env("POSTGRES_CONTROL_PLANE_DB")
    found = _exec_psql(
        "postgres-control-plane", user, db, _table_list_query()
    )
    assert found == "", (
        f"control-plane should have no runner-substrate tables; "
        f"psql reported {found!r}"
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


def _make_gold_set_with_finalized_revision(
    *, tenant_id: uuid.UUID
) -> tuple[GoldSet, GoldSetRevision, GoldSetEntry]:
    gs_id = uuid4()
    rev_id = uuid4()
    finalized_at = datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc)
    gold_set = GoldSet(
        id=gs_id,
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        name=f"iso-runner-{uuid4().hex[:8]}",
        created_by_user_id="iso-test",
        created_at=finalized_at,
        current_revision_id=rev_id,
    )
    revision = GoldSetRevision(
        id=rev_id,
        gold_set_id=gs_id,
        revision_number=1,
        status=GoldSetRevisionStatus.FINALIZED,
        created_by_user_id="iso-test",
        created_at=finalized_at,
        finalized_at=finalized_at,
        # 64-char hex stand-ins; the chain primitive's contract is
        # length-64 hex per the schema CHECK in migration 0013.
        this_event_hash="a" * 64,
        previous_event_hash="0" * 64,
    )
    entry = GoldSetEntry(
        id=uuid4(),
        gold_set_revision_id=rev_id,
        entry_index=0,
        query="x",
        expected_chunk_ids=(uuid4(),),
    )
    return gold_set, revision, entry


def _make_evaluation_run(
    *,
    tenant_id: uuid.UUID,
    gold_set_id: uuid.UUID,
    gold_set_revision_id: uuid.UUID,
    status: EvaluationRunStatus = EvaluationRunStatus.RUNNING,
    completed_at: datetime | None = None,
) -> EvaluationRun:
    invoked_at = datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc)
    return EvaluationRun(
        id=uuid4(),
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        gold_set_id=gold_set_id,
        gold_set_revision_id=gold_set_revision_id,
        invoked_by_user_id="iso-test",
        invoked_at=invoked_at,
        completed_at=completed_at,
        status=status,
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
    control-plane Postgres, apply the per-tenant Alembic chain to each,
    and yield (tenant_a_uuid, tenant_b_uuid, sm_a, sm_b)."""
    settings = _cp_settings()
    suffix = uuid.uuid4().hex[:8]
    tenant_a_db = f"eval_run_iso_a_{suffix}"
    tenant_b_db = f"eval_run_iso_b_{suffix}"
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


def _build_runner_repo(
    *, bound_tenant_id: uuid.UUID, sm
) -> PostgresEvaluationRunRepository:
    async def resolver(_tid: TenantId):
        return sm
    return PostgresEvaluationRunRepository(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=TenantId(str(bound_tenant_id)),
    )


def _build_runner_reader(
    *, bound_tenant_id: uuid.UUID, sm
) -> PostgresEvaluationRunReader:
    async def resolver(_tid: TenantId):
        return sm
    return PostgresEvaluationRunReader(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=TenantId(str(bound_tenant_id)),
    )


def _build_gold_set_repo(
    *, bound_tenant_id: uuid.UUID, sm
) -> PostgresGoldSetRepository:
    async def resolver(_tid: TenantId):
        return sm
    return PostgresGoldSetRepository(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=TenantId(str(bound_tenant_id)),
    )


def _tenant_context(tenant_id: uuid.UUID) -> TenantContext:
    return TenantContext(
        tenant_id=str(tenant_id),
        jurisdiction="eu-west",
        cost_attribution_id=str(tenant_id),
    )


def _seed_finalized_gold_set_on_tenant(
    *,
    event_loop,
    tenant_id: uuid.UUID,
    sm,
) -> tuple[GoldSet, GoldSetRevision, GoldSetEntry]:
    """Persist a finalized gold-set + revision + one entry on the
    given tenant's DB, bypassing the application use case's
    canonical-payload-hash machinery for test setup speed."""
    gold_set, revision, entry = _make_gold_set_with_finalized_revision(
        tenant_id=tenant_id
    )
    # Insert raw rows directly so the fixture is independent of the
    # gold-set application use cases (which would also work but bring
    # in hash-chain primitives the isolation contract doesn't exercise).
    async def _go() -> None:
        async with sm() as session:
            async with session.begin():
                await session.execute(
                    sa.text(
                        "INSERT INTO gold_sets ("
                        "id, tenant_id, jurisdiction, name, "
                        "created_by_user_id, created_at, "
                        "current_revision_id) VALUES ("
                        ":id, :tid, :j, :n, :u, :ts, NULL)"
                    ),
                    {
                        "id": str(gold_set.id),
                        "tid": str(gold_set.tenant_id),
                        "j": gold_set.jurisdiction,
                        "n": gold_set.name,
                        "u": gold_set.created_by_user_id,
                        "ts": gold_set.created_at,
                    },
                )
                await session.execute(
                    sa.text(
                        "INSERT INTO gold_set_revisions ("
                        "id, gold_set_id, revision_number, status, "
                        "created_by_user_id, created_at, finalized_at, "
                        "this_event_hash, previous_event_hash) VALUES ("
                        ":id, :gsid, 1, 'finalized', :u, :ts, :ts, "
                        ":this, :prev)"
                    ),
                    {
                        "id": str(revision.id),
                        "gsid": str(revision.gold_set_id),
                        "u": revision.created_by_user_id,
                        "ts": revision.finalized_at,
                        "this": revision.this_event_hash,
                        "prev": revision.previous_event_hash,
                    },
                )
                await session.execute(
                    sa.text(
                        "UPDATE gold_sets SET current_revision_id = :rid "
                        "WHERE id = :gsid"
                    ),
                    {"rid": str(revision.id), "gsid": str(gold_set.id)},
                )
                await session.execute(
                    sa.text(
                        "INSERT INTO gold_set_entries ("
                        "id, gold_set_revision_id, entry_index, query, "
                        "expected_chunk_ids) VALUES ("
                        ":id, :rid, 0, :q, :ec)"
                    ),
                    {
                        "id": str(entry.id),
                        "rid": str(revision.id),
                        "q": entry.query,
                        "ec": [str(c) for c in entry.expected_chunk_ids],
                    },
                )
    event_loop.run_until_complete(_go())
    return gold_set, revision, entry


def test_persist_run_isolated_per_tenant(event_loop, isolation_setup) -> None:
    """Cross-tenant write isolation: a tenant-A run lands on tenant_a's
    DB only; tenant_b's evaluation_runs remains empty."""
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    gs_a, rev_a, _entry_a = _seed_finalized_gold_set_on_tenant(
        event_loop=event_loop, tenant_id=tenant_a, sm=sm_a
    )
    repo = _build_runner_repo(bound_tenant_id=tenant_a, sm=sm_a)
    run = _make_evaluation_run(
        tenant_id=tenant_a, gold_set_id=gs_a.id, gold_set_revision_id=rev_a.id
    )

    event_loop.run_until_complete(
        repo.persist_run(tenant_context=_tenant_context(tenant_a), run=run)
    )

    assert _row_count(event_loop, sm_a, evaluation_runs) == 1
    assert _row_count(event_loop, sm_b, evaluation_runs) == 0


def test_adapter_rejects_tenant_context_mismatch(
    event_loop, isolation_setup
) -> None:
    """Defence-in-depth per D24 / D32: a call with a TenantContext
    whose tenant_id doesn't match the bound tenant raises ValueError
    before any session resolution."""
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    gs_a, rev_a, _entry_a = _seed_finalized_gold_set_on_tenant(
        event_loop=event_loop, tenant_id=tenant_a, sm=sm_a
    )
    repo_for_a = _build_runner_repo(bound_tenant_id=tenant_a, sm=sm_a)
    run = _make_evaluation_run(
        tenant_id=tenant_b, gold_set_id=gs_a.id, gold_set_revision_id=rev_a.id
    )

    with pytest.raises(ValueError, match="tenant"):
        event_loop.run_until_complete(
            repo_for_a.persist_run(
                tenant_context=_tenant_context(tenant_b), run=run
            )
        )

    assert _row_count(event_loop, sm_a, evaluation_runs) == 0


def test_adapter_rejects_evaluation_run_tenant_mismatch(
    event_loop, isolation_setup
) -> None:
    """Second defence-in-depth: even with matching TenantContext, an
    EvaluationRun whose own tenant_id differs from the bound tenant
    is rejected. Guards against assembly bugs."""
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    gs_a, rev_a, _entry_a = _seed_finalized_gold_set_on_tenant(
        event_loop=event_loop, tenant_id=tenant_a, sm=sm_a
    )
    repo_for_a = _build_runner_repo(bound_tenant_id=tenant_a, sm=sm_a)
    run = _make_evaluation_run(
        tenant_id=tenant_b, gold_set_id=gs_a.id, gold_set_revision_id=rev_a.id
    )

    with pytest.raises(ValueError, match="tenant"):
        event_loop.run_until_complete(
            repo_for_a.persist_run(
                tenant_context=_tenant_context(tenant_a), run=run
            )
        )

    assert _row_count(event_loop, sm_a, evaluation_runs) == 0


def test_cross_tenant_get_run_returns_none(
    event_loop, isolation_setup
) -> None:
    """A run persisted on tenant_a is invisible to a tenant_b-bound
    reader: the adapter routes to tenant_b's DB where the row doesn't
    exist."""
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    gs_a, rev_a, _entry_a = _seed_finalized_gold_set_on_tenant(
        event_loop=event_loop, tenant_id=tenant_a, sm=sm_a
    )
    repo_a = _build_runner_repo(bound_tenant_id=tenant_a, sm=sm_a)
    run = _make_evaluation_run(
        tenant_id=tenant_a, gold_set_id=gs_a.id, gold_set_revision_id=rev_a.id
    )
    event_loop.run_until_complete(
        repo_a.persist_run(tenant_context=_tenant_context(tenant_a), run=run)
    )

    reader_b = _build_runner_reader(bound_tenant_id=tenant_b, sm=sm_b)
    snapshot = event_loop.run_until_complete(
        reader_b.get_run_with_results_and_aggregates(
            tenant_context=_tenant_context(tenant_b), run_id=run.id
        )
    )
    assert snapshot is None


def test_cross_tenant_list_runs_returns_empty(
    event_loop, isolation_setup
) -> None:
    """Tenant-B's list view never includes tenant-A's runs."""
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    gs_a, rev_a, _entry_a = _seed_finalized_gold_set_on_tenant(
        event_loop=event_loop, tenant_id=tenant_a, sm=sm_a
    )
    repo_a = _build_runner_repo(bound_tenant_id=tenant_a, sm=sm_a)
    for _ in range(2):
        run = _make_evaluation_run(
            tenant_id=tenant_a, gold_set_id=gs_a.id,
            gold_set_revision_id=rev_a.id,
        )
        event_loop.run_until_complete(
            repo_a.persist_run(tenant_context=_tenant_context(tenant_a), run=run)
        )

    reader_b = _build_runner_reader(bound_tenant_id=tenant_b, sm=sm_b)
    page = event_loop.run_until_complete(
        reader_b.list_runs(
            tenant_context=_tenant_context(tenant_b),
            cursor=None,
            page_size=10,
        )
    )
    assert page.runs == ()
    assert page.next_cursor is None


def test_cross_tenant_mark_completed_does_not_transition(
    event_loop, isolation_setup
) -> None:
    """mark_completed against a run owned by tenant_a, called through
    a tenant_b-bound adapter, raises ValueError (rowcount=0) and
    leaves the original row untouched (still 'running')."""
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    gs_a, rev_a, _entry_a = _seed_finalized_gold_set_on_tenant(
        event_loop=event_loop, tenant_id=tenant_a, sm=sm_a
    )
    repo_a = _build_runner_repo(bound_tenant_id=tenant_a, sm=sm_a)
    run = _make_evaluation_run(
        tenant_id=tenant_a, gold_set_id=gs_a.id, gold_set_revision_id=rev_a.id
    )
    event_loop.run_until_complete(
        repo_a.persist_run(tenant_context=_tenant_context(tenant_a), run=run)
    )

    repo_b = _build_runner_repo(bound_tenant_id=tenant_b, sm=sm_b)
    with pytest.raises(ValueError):
        event_loop.run_until_complete(
            repo_b.mark_completed(
                tenant_context=_tenant_context(tenant_b),
                run_id=run.id,
                completed_at=datetime(2026, 5, 15, 13, tzinfo=timezone.utc),
            )
        )

    # Run on tenant_a still 'running'
    async def _read_status() -> str:
        async with sm_a() as session:
            return (
                await session.execute(
                    sa.select(evaluation_runs.c.status).where(
                        evaluation_runs.c.id == str(run.id)
                    )
                )
            ).scalar_one()

    assert event_loop.run_until_complete(_read_status()) == "running"


def test_cross_tenant_result_persist_blocked_by_fk(
    event_loop, isolation_setup
) -> None:
    """A result row carrying a tenant-A run_id cannot be inserted on
    tenant_b's DB: the FK to evaluation_runs(id) fails because the
    parent row doesn't exist on tenant_b. Structural isolation via
    per-tenant DB topology per D32 enforces this at the SQL layer."""
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    gs_a, rev_a, entry_a = _seed_finalized_gold_set_on_tenant(
        event_loop=event_loop, tenant_id=tenant_a, sm=sm_a
    )
    repo_a = _build_runner_repo(bound_tenant_id=tenant_a, sm=sm_a)
    run = _make_evaluation_run(
        tenant_id=tenant_a, gold_set_id=gs_a.id, gold_set_revision_id=rev_a.id
    )
    event_loop.run_until_complete(
        repo_a.persist_run(tenant_context=_tenant_context(tenant_a), run=run)
    )

    repo_b = _build_runner_repo(bound_tenant_id=tenant_b, sm=sm_b)
    orphan_result = EvaluationResult(
        id=uuid4(),
        evaluation_run_id=run.id,  # belongs to tenant_a
        gold_set_entry_id=entry_a.id,
        retrieval_strategy="vector_only",
        returned_chunk_ids=(uuid4(),),
        recall_at_k={1: 0.0, 3: 0.0, 5: 0.0, 10: 0.0},
        precision_at_k={1: 0.0, 3: 0.0, 5: 0.0, 10: 0.0},
        mrr=Decimal("0.0000"),
        latency_ms=10,
    )
    with pytest.raises(Exception):
        event_loop.run_until_complete(
            repo_b.persist_result(
                tenant_context=_tenant_context(tenant_b),
                result=orphan_result,
            )
        )
    assert _row_count(event_loop, sm_b, evaluation_results) == 0


def test_cross_tenant_aggregate_persist_blocked_by_fk(
    event_loop, isolation_setup
) -> None:
    """An aggregate row carrying a tenant-A run_id cannot be inserted
    on tenant_b's DB: same FK structural enforcement as results."""
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    gs_a, rev_a, _entry_a = _seed_finalized_gold_set_on_tenant(
        event_loop=event_loop, tenant_id=tenant_a, sm=sm_a
    )
    repo_a = _build_runner_repo(bound_tenant_id=tenant_a, sm=sm_a)
    run = _make_evaluation_run(
        tenant_id=tenant_a, gold_set_id=gs_a.id, gold_set_revision_id=rev_a.id
    )
    event_loop.run_until_complete(
        repo_a.persist_run(tenant_context=_tenant_context(tenant_a), run=run)
    )

    repo_b = _build_runner_repo(bound_tenant_id=tenant_b, sm=sm_b)
    orphan_aggregate = EvaluationAggregate(
        id=uuid4(),
        evaluation_run_id=run.id,
        retrieval_strategy="vector_only",
        recall_at_k_mean={1: 0.0, 3: 0.0, 5: 0.0, 10: 0.0},
        precision_at_k_mean={1: 0.0, 3: 0.0, 5: 0.0, 10: 0.0},
        mrr_mean=Decimal("0.0000"),
        latency_ms_p50=0,
        latency_ms_p95=0,
        latency_ms_mean=0,
    )
    with pytest.raises(Exception):
        event_loop.run_until_complete(
            repo_b.persist_aggregate(
                tenant_context=_tenant_context(tenant_b),
                aggregate=orphan_aggregate,
            )
        )
    assert _row_count(event_loop, sm_b, evaluation_aggregates) == 0


def test_run_persist_blocked_when_gold_set_lives_on_other_tenant(
    event_loop, isolation_setup
) -> None:
    """If a runner attempts to persist a run on tenant_b that
    references a gold_set_id owned by tenant_a, the FK to gold_sets
    fails because tenant_b's DB doesn't carry that gold_set row.
    Brief Finding-5 commitment: cross-tenant run-to-gold-set
    association is structurally impossible."""
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    gs_a, rev_a, _entry_a = _seed_finalized_gold_set_on_tenant(
        event_loop=event_loop, tenant_id=tenant_a, sm=sm_a
    )
    repo_b = _build_runner_repo(bound_tenant_id=tenant_b, sm=sm_b)
    cross_run = _make_evaluation_run(
        tenant_id=tenant_b,  # passes the adapter's bound-check
        gold_set_id=gs_a.id,  # but references tenant_a's gold-set
        gold_set_revision_id=rev_a.id,
    )

    with pytest.raises(Exception):
        event_loop.run_until_complete(
            repo_b.persist_run(
                tenant_context=_tenant_context(tenant_b), run=cross_run
            )
        )
    assert _row_count(event_loop, sm_b, evaluation_runs) == 0
