"""Tenant isolation contract tests for the optimization context (D24, D32, D111).

Per D32, per-tenant data planes are independent Postgres instances.
Per D111, the three optimization-substrate tables
(``optimization_runs``, ``recommendations``,
``recommendation_status_transitions``) live on each tenant's database,
NOT on the control plane.

Two layers mirroring ``test_evaluation_run_isolation.py``:

1. Structural isolation: each tenant's DB carries the three tables
   from migration 0015; the control-plane DB does not.

2. Behavioural cross-tenant isolation: a tenant-A run / recommendation
   persisted via the Postgres adapters lands on tenant_a's DB only;
   tenant_b's DB stays empty. Cross-tenant reads return None.
   Defence-in-depth ValueError fires on TenantContext or
   ``Recommendation.tenant_id`` mismatch. The status-transition
   refuses to fire when the recommendation is not owned by the bound
   tenant. FK from ``recommendations`` to ``optimization_runs`` on
   the same DB makes cross-tenant association structurally
   impossible.

Synthetic dual-tenant fixture provisions two databases on the
loopback control-plane Postgres (S5 host-port-binding exception);
the resolver maps each test tenant_id to its sessionmaker.
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

from contexts.optimization.adapters.outbound.postgres._tables import (
    optimization_runs,
    recommendation_status_transitions,
    recommendations,
)
from contexts.optimization.adapters.outbound.postgres.optimization_run_reader import (
    PostgresOptimizationRunReader,
)
from contexts.optimization.adapters.outbound.postgres.optimization_run_repository import (
    PostgresOptimizationRunRepository,
)
from contexts.optimization.adapters.outbound.postgres.recommendation_reader import (
    PostgresRecommendationReader,
)
from contexts.optimization.adapters.outbound.postgres.recommendation_repository import (
    PostgresRecommendationRepository,
)
from contexts.optimization.domain import (
    OptimizationRun,
    OptimizationRunStatus,
    Recommendation,
    RecommendationCategory,
    RecommendationStatus,
    RecommendationStatusTransition,
    RetrievalStrategyEvidenceCitation,
    StrategyComparison,
)
from padhanam.config import ControlPlaneSettings
from shared_kernel import TenantContext, TenantId


_OPTIMIZATION_TABLES = (
    "optimization_runs",
    "recommendation_status_transitions",
    "recommendations",
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
    in_clause = ", ".join(f"'{t}'" for t in _OPTIMIZATION_TABLES)
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
def test_per_tenant_db_has_all_three_optimization_tables(
    compose_running: None,
    service: str,
    user_env: str,
    db_env: str,
) -> None:
    """D32 / D111: each tenant's DB carries the three optimization tables."""
    user = _env(user_env)
    db = _env(db_env)
    found = set(
        _exec_psql(service, user, db, _table_list_query()).splitlines()
    )
    assert found == set(_OPTIMIZATION_TABLES), (
        f"per-tenant DB {service} missing optimization tables; "
        f"found {sorted(found)}"
    )


def test_control_plane_db_has_no_optimization_tables(
    compose_running: None,
) -> None:
    """D32 / D111: control-plane has no optimization tables. Recommendation
    records are platform-computed against per-tenant evidence; control-
    plane storage would violate D32."""
    user = _env("POSTGRES_CONTROL_PLANE_USER")
    db = _env("POSTGRES_CONTROL_PLANE_DB")
    found = _exec_psql(
        "postgres-control-plane", user, db, _table_list_query()
    )
    assert found == "", (
        f"control-plane should have no optimization tables; "
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
    tenant_a_db = f"opt_iso_a_{suffix}"
    tenant_b_db = f"opt_iso_b_{suffix}"
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


def _tenant_context(tenant_id: uuid.UUID) -> TenantContext:
    return TenantContext(
        tenant_id=str(tenant_id),
        jurisdiction="eu-west",
        cost_attribution_id=str(tenant_id),
    )


def _build_run_repo(*, bound: uuid.UUID, sm) -> PostgresOptimizationRunRepository:
    async def resolver(_tid: TenantId):
        return sm
    return PostgresOptimizationRunRepository(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=TenantId(str(bound)),
    )


def _build_run_reader(*, bound: uuid.UUID, sm) -> PostgresOptimizationRunReader:
    async def resolver(_tid: TenantId):
        return sm
    return PostgresOptimizationRunReader(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=TenantId(str(bound)),
    )


def _build_rec_repo(*, bound: uuid.UUID, sm) -> PostgresRecommendationRepository:
    async def resolver(_tid: TenantId):
        return sm
    return PostgresRecommendationRepository(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=TenantId(str(bound)),
    )


def _build_rec_reader(*, bound: uuid.UUID, sm) -> PostgresRecommendationReader:
    async def resolver(_tid: TenantId):
        return sm
    return PostgresRecommendationReader(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=TenantId(str(bound)),
    )


def _make_run(*, tenant_id: uuid.UUID) -> OptimizationRun:
    invoked_at = datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc)
    return OptimizationRun(
        id=uuid4(),
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        invoked_by_user_id="iso-test",
        invoked_at=invoked_at,
        completed_at=None,
        status=OptimizationRunStatus.RUNNING,
    )


def _make_citation() -> RetrievalStrategyEvidenceCitation:
    return RetrievalStrategyEvidenceCitation(
        evaluation_run_id=uuid4(),
        gold_set_id=uuid4(),
        comparison=StrategyComparison(
            strategy_a="graph_only",
            strategy_b="vector_only",
            recall_at_k_delta={1: 0.4, 3: 0.8, 5: 0.87, 10: 1.0},
            precision_at_k_delta={1: 1.0, 3: 0.67, 5: 0.47, 10: 0.3},
        ),
    )


def _make_recommendation(
    *,
    tenant_id: uuid.UUID,
    generated_by_run_id: uuid.UUID,
) -> Recommendation:
    now = datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc)
    return Recommendation(
        id=uuid4(),
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        category=RecommendationCategory.RETRIEVAL_STRATEGY,
        subject="iso test",
        text="iso test text",
        evidence_citations=(_make_citation(),),
        status=RecommendationStatus.GENERATED,
        generated_at=now,
        generated_by_run_id=generated_by_run_id,
        last_transition_at=now,
        last_transition_by_user_id=None,
    )


def _seed_run(*, event_loop, tenant_id, sm) -> OptimizationRun:
    run = _make_run(tenant_id=tenant_id)
    repo = _build_run_repo(bound=tenant_id, sm=sm)
    event_loop.run_until_complete(
        repo.persist_run(tenant_context=_tenant_context(tenant_id), run=run)
    )
    return run


def _seed_recommendation(
    *, event_loop, tenant_id, sm, run_id
) -> Recommendation:
    rec = _make_recommendation(
        tenant_id=tenant_id, generated_by_run_id=run_id
    )
    repo = _build_rec_repo(bound=tenant_id, sm=sm)
    event_loop.run_until_complete(
        repo.persist_recommendation(
            tenant_context=_tenant_context(tenant_id), recommendation=rec
        )
    )
    return rec


# --- Scenarios ---


def test_persist_run_isolated_per_tenant(
    event_loop, isolation_setup
) -> None:
    """Cross-tenant write isolation: a tenant-A run lands on tenant_a's
    DB only; tenant_b's optimization_runs remains empty."""
    tenant_a, _tenant_b, sm_a, sm_b = isolation_setup
    _seed_run(event_loop=event_loop, tenant_id=tenant_a, sm=sm_a)
    assert _row_count(event_loop, sm_a, optimization_runs) == 1
    assert _row_count(event_loop, sm_b, optimization_runs) == 0


def test_persist_recommendation_isolated_per_tenant(
    event_loop, isolation_setup
) -> None:
    """A tenant-A recommendation lands on tenant_a's DB only."""
    tenant_a, _tenant_b, sm_a, sm_b = isolation_setup
    run = _seed_run(event_loop=event_loop, tenant_id=tenant_a, sm=sm_a)
    _seed_recommendation(
        event_loop=event_loop, tenant_id=tenant_a, sm=sm_a, run_id=run.id
    )
    assert _row_count(event_loop, sm_a, recommendations) == 1
    assert _row_count(event_loop, sm_b, recommendations) == 0


def test_get_recommendation_cross_tenant_returns_none(
    event_loop, isolation_setup
) -> None:
    """Cross-tenant get returns None for the foreign reader's bound tenant."""
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    run = _seed_run(event_loop=event_loop, tenant_id=tenant_a, sm=sm_a)
    rec = _seed_recommendation(
        event_loop=event_loop, tenant_id=tenant_a, sm=sm_a, run_id=run.id
    )
    reader_for_b = _build_rec_reader(bound=tenant_b, sm=sm_b)
    fetched = event_loop.run_until_complete(
        reader_for_b.get_recommendation(
            tenant_context=_tenant_context(tenant_b),
            recommendation_id=rec.id,
        )
    )
    assert fetched is None


def test_list_recommendations_cross_tenant_returns_empty(
    event_loop, isolation_setup
) -> None:
    """Cross-tenant list returns empty page."""
    from contexts.optimization.domain.query_filters import (
        RecommendationListFilters,
    )

    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    run = _seed_run(event_loop=event_loop, tenant_id=tenant_a, sm=sm_a)
    _seed_recommendation(
        event_loop=event_loop, tenant_id=tenant_a, sm=sm_a, run_id=run.id
    )
    reader_for_b = _build_rec_reader(bound=tenant_b, sm=sm_b)
    page = event_loop.run_until_complete(
        reader_for_b.list_recommendations(
            tenant_context=_tenant_context(tenant_b),
            filters=RecommendationListFilters(),
            cursor=None,
            page_size=20,
        )
    )
    assert page.recommendations == ()


def test_get_optimization_run_cross_tenant_returns_none(
    event_loop, isolation_setup
) -> None:
    """Cross-tenant optimization-run get returns None."""
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    run = _seed_run(event_loop=event_loop, tenant_id=tenant_a, sm=sm_a)
    reader_for_b = _build_run_reader(bound=tenant_b, sm=sm_b)
    snapshot = event_loop.run_until_complete(
        reader_for_b.get_optimization_run(
            tenant_context=_tenant_context(tenant_b),
            run_id=run.id,
        )
    )
    assert snapshot is None


def test_adapter_rejects_tenant_context_mismatch(
    event_loop, isolation_setup
) -> None:
    """Defence-in-depth: TenantContext mismatch raises ValueError before
    any session resolution."""
    tenant_a, tenant_b, sm_a, _sm_b = isolation_setup
    repo_for_a = _build_run_repo(bound=tenant_a, sm=sm_a)
    run = _make_run(tenant_id=tenant_b)
    with pytest.raises(ValueError, match="tenant"):
        event_loop.run_until_complete(
            repo_for_a.persist_run(
                tenant_context=_tenant_context(tenant_b), run=run
            )
        )
    assert _row_count(event_loop, sm_a, optimization_runs) == 0


def test_adapter_rejects_recommendation_tenant_mismatch(
    event_loop, isolation_setup
) -> None:
    """Second defence-in-depth: Recommendation.tenant_id differs from
    bound is rejected even with matching TenantContext."""
    tenant_a, tenant_b, sm_a, _sm_b = isolation_setup
    run = _seed_run(event_loop=event_loop, tenant_id=tenant_a, sm=sm_a)
    repo_for_a = _build_rec_repo(bound=tenant_a, sm=sm_a)
    foreign_rec = _make_recommendation(
        tenant_id=tenant_b, generated_by_run_id=run.id
    )
    with pytest.raises(ValueError, match="tenant"):
        event_loop.run_until_complete(
            repo_for_a.persist_recommendation(
                tenant_context=_tenant_context(tenant_a),
                recommendation=foreign_rec,
            )
        )
    assert _row_count(event_loop, sm_a, recommendations) == 0


def test_status_transition_rejects_cross_tenant_recommendation(
    event_loop, isolation_setup
) -> None:
    """Cross-tenant transition: the bound-to-A repository refuses to
    transition a tenant-B-owned recommendation. The UPDATE's WHERE
    clause pins tenant_id=A AND status='generated'; rowcount=0 raises."""
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    run_b = _seed_run(event_loop=event_loop, tenant_id=tenant_b, sm=sm_b)
    rec_b = _seed_recommendation(
        event_loop=event_loop, tenant_id=tenant_b, sm=sm_b, run_id=run_b.id
    )
    repo_for_a = _build_rec_repo(bound=tenant_a, sm=sm_a)
    now = datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc)
    updated = Recommendation(
        id=rec_b.id,
        tenant_id=tenant_a,  # spoofed
        jurisdiction="eu-west",
        category=rec_b.category,
        subject=rec_b.subject,
        text=rec_b.text,
        evidence_citations=rec_b.evidence_citations,
        status=RecommendationStatus.ACKNOWLEDGED,
        generated_at=rec_b.generated_at,
        generated_by_run_id=rec_b.generated_by_run_id,
        last_transition_at=now,
        last_transition_by_user_id="attacker",
    )
    transition = RecommendationStatusTransition(
        id=uuid4(),
        recommendation_id=rec_b.id,
        from_status=RecommendationStatus.GENERATED,
        to_status=RecommendationStatus.ACKNOWLEDGED,
        transitioned_by_user_id="attacker",
        transitioned_at=now,
    )
    with pytest.raises(ValueError):
        event_loop.run_until_complete(
            repo_for_a.persist_status_transition(
                tenant_context=_tenant_context(tenant_a),
                updated_recommendation=updated,
                transition=transition,
            )
        )
    # tenant_b's transition table remains empty
    assert _row_count(event_loop, sm_b, recommendation_status_transitions) == 0
