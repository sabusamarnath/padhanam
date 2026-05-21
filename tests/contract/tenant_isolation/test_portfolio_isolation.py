"""Tenant isolation contract tests for the portfolio context (D24, D32, D124).

Per D32, per-tenant data planes are independent Postgres instances.
Per D124, the three portfolio-substrate tables (``cases``,
``data_points``, ``assertions``) live on each tenant's database.

Behavioural cross-tenant isolation plus adapter round-trips: entities
persisted via the Postgres adapters land on the owning tenant's DB
only; cross-tenant reads return None / empty; the defence-in-depth
ValueError fires on TenantContext or entity tenant_id mismatch.
Round-trip, ordering, and cursor-pagination scenarios exercise the
repository and reader.

The synthetic dual-tenant fixture provisions two databases on the
loopback control-plane Postgres (S5 host-port-binding exception) and
applies the per-tenant Alembic chain (head = 0016) to each; the
resolver maps each test tenant_id to its sessionmaker. The structural
"migration deployed to the real per-tenant containers" check lands
with the S43 live-stack smoke (commit 9).
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from contexts.portfolio.adapters.outbound.postgres._tables import (
    assertions as assertions_table,
)
from contexts.portfolio.adapters.outbound.postgres._tables import (
    cases as cases_table,
)
from contexts.portfolio.adapters.outbound.postgres.portfolio_reader import (
    PostgresPortfolioReader,
)
from contexts.portfolio.adapters.outbound.postgres.portfolio_repository import (
    PostgresPortfolioRepository,
)
from contexts.portfolio.domain import (
    Assertion,
    AssertionType,
    Case,
    CaseStatus,
    CaseType,
    DataPoint,
    DataPointType,
)
from contexts.portfolio.domain.query_filters import CaseListFilters
from padhanam.config import ControlPlaneSettings
from shared_kernel import ActorReference, AssertionChange, TenantContext, TenantId

_ACTOR = ActorReference(user_id="iso-test")

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
    tenant_a_db = f"pf_iso_a_{suffix}"
    tenant_b_db = f"pf_iso_b_{suffix}"
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


def _run(event_loop, coro):
    return event_loop.run_until_complete(coro)


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


def _build_repo(*, bound: uuid.UUID, sm) -> PostgresPortfolioRepository:
    async def resolver(_tid: TenantId):
        return sm
    return PostgresPortfolioRepository(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=TenantId(str(bound)),
    )


def _build_reader(*, bound: uuid.UUID, sm) -> PostgresPortfolioReader:
    async def resolver(_tid: TenantId):
        return sm
    return PostgresPortfolioReader(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=TenantId(str(bound)),
    )


_BASE_TS = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_case(
    *, tenant_id: uuid.UUID, created_at: datetime | None = None,
    status: CaseStatus = CaseStatus.OPEN, title: str = "iso case",
) -> Case:
    ts = created_at or _BASE_TS
    return Case(
        id=uuid4(),
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        title=title,
        case_type=CaseType.PORTFOLIO_ITEM,
        status=status,
        created_at=ts,
        updated_at=ts,
    )


def _make_data_point(*, tenant_id: uuid.UUID, case_id: uuid.UUID) -> DataPoint:
    dp_id = uuid4()
    initial = Assertion(
        id=uuid4(),
        data_point_id=dp_id,
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        assertion_type=AssertionType.INITIAL,
        revises_assertion_id=None,
        value={"progress": 0},
        authored_by=_ACTOR,
        created_at=_BASE_TS,
    )
    return DataPoint(
        id=dp_id,
        case_id=case_id,
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        data_point_type=DataPointType.GOAL,
        value={"progress": 0},
        authored_by=_ACTOR,
        created_at=_BASE_TS,
        assertions=(initial,),
    )


def _seed_case(*, event_loop, tenant_id, sm, **kw) -> Case:
    case = _make_case(tenant_id=tenant_id, **kw)
    repo = _build_repo(bound=tenant_id, sm=sm)
    _run(event_loop, repo.save_case(
        tenant_context=_tenant_context(tenant_id), case=case))
    return case


def _seed_data_point(*, event_loop, tenant_id, sm, case_id) -> DataPoint:
    dp = _make_data_point(tenant_id=tenant_id, case_id=case_id)
    repo = _build_repo(bound=tenant_id, sm=sm)
    _run(event_loop, repo.save_data_point(
        tenant_context=_tenant_context(tenant_id), data_point=dp))
    return dp


# --- round-trip scenarios ---


def test_save_and_get_case_round_trip(event_loop, isolation_setup) -> None:
    tenant_a, _b, sm_a, _sm_b = isolation_setup
    case = _seed_case(event_loop=event_loop, tenant_id=tenant_a, sm=sm_a)
    reader = _build_reader(bound=tenant_a, sm=sm_a)
    fetched = _run(event_loop, reader.get_case(
        tenant_context=_tenant_context(tenant_a), case_id=case.id))
    assert fetched is not None
    assert fetched.id == case.id
    assert fetched.title == case.title
    assert fetched.status is CaseStatus.OPEN


def test_save_and_get_data_point_with_initial_assertion(
    event_loop, isolation_setup
) -> None:
    tenant_a, _b, sm_a, _sm_b = isolation_setup
    case = _seed_case(event_loop=event_loop, tenant_id=tenant_a, sm=sm_a)
    dp = _seed_data_point(
        event_loop=event_loop, tenant_id=tenant_a, sm=sm_a, case_id=case.id)
    reader = _build_reader(bound=tenant_a, sm=sm_a)
    fetched = _run(event_loop, reader.get_data_point(
        tenant_context=_tenant_context(tenant_a), data_point_id=dp.id))
    assert fetched is not None
    assert len(fetched.assertions) == 1
    assert fetched.assertions[0].assertion_type is AssertionType.INITIAL
    assert fetched.current_value == {"progress": 0}


def test_revise_persists_and_history_is_ordered(
    event_loop, isolation_setup
) -> None:
    tenant_a, _b, sm_a, _sm_b = isolation_setup
    case = _seed_case(event_loop=event_loop, tenant_id=tenant_a, sm=sm_a)
    dp = _seed_data_point(
        event_loop=event_loop, tenant_id=tenant_a, sm=sm_a, case_id=case.id)
    revised = dp.revise(AssertionChange(value={"progress": 60}), _ACTOR)
    repo = _build_repo(bound=tenant_a, sm=sm_a)
    _run(event_loop, repo.save_assertion(
        tenant_context=_tenant_context(tenant_a),
        assertion=revised.assertions[-1]))
    reader = _build_reader(bound=tenant_a, sm=sm_a)
    history = _run(event_loop, reader.assertion_history(
        tenant_context=_tenant_context(tenant_a), data_point_id=dp.id))
    assert [a.assertion_type for a in history] == [
        AssertionType.INITIAL, AssertionType.REVISION]
    assert history[1].value == {"progress": 60}
    assert history[1].revises_assertion_id == history[0].id


def test_list_cases_cursor_pagination(event_loop, isolation_setup) -> None:
    tenant_a, _b, sm_a, _sm_b = isolation_setup
    for i in range(3):
        _seed_case(
            event_loop=event_loop, tenant_id=tenant_a, sm=sm_a,
            created_at=_BASE_TS + timedelta(hours=i), title=f"case {i}")
    reader = _build_reader(bound=tenant_a, sm=sm_a)
    page1 = _run(event_loop, reader.list_cases(
        tenant_context=_tenant_context(tenant_a),
        filters=None, cursor=None, page_size=2))
    assert len(page1.cases) == 2
    assert page1.next_cursor is not None
    page2 = _run(event_loop, reader.list_cases(
        tenant_context=_tenant_context(tenant_a),
        filters=None, cursor=page1.next_cursor, page_size=2))
    assert len(page2.cases) == 1
    assert page2.next_cursor is None
    all_titles = [c.title for c in page1.cases] + [c.title for c in page2.cases]
    assert all_titles == ["case 2", "case 1", "case 0"]


def test_list_cases_status_filter(event_loop, isolation_setup) -> None:
    tenant_a, _b, sm_a, _sm_b = isolation_setup
    _seed_case(event_loop=event_loop, tenant_id=tenant_a, sm=sm_a,
               status=CaseStatus.OPEN)
    _seed_case(event_loop=event_loop, tenant_id=tenant_a, sm=sm_a,
               status=CaseStatus.ARCHIVED,
               created_at=_BASE_TS + timedelta(hours=1))
    reader = _build_reader(bound=tenant_a, sm=sm_a)
    page = _run(event_loop, reader.list_cases(
        tenant_context=_tenant_context(tenant_a),
        filters=CaseListFilters(statuses=(CaseStatus.ARCHIVED,)),
        cursor=None, page_size=20))
    assert len(page.cases) == 1
    assert page.cases[0].status is CaseStatus.ARCHIVED


def test_list_data_points_returns_case_children(
    event_loop, isolation_setup
) -> None:
    tenant_a, _b, sm_a, _sm_b = isolation_setup
    case = _seed_case(event_loop=event_loop, tenant_id=tenant_a, sm=sm_a)
    _seed_data_point(
        event_loop=event_loop, tenant_id=tenant_a, sm=sm_a, case_id=case.id)
    _seed_data_point(
        event_loop=event_loop, tenant_id=tenant_a, sm=sm_a, case_id=case.id)
    reader = _build_reader(bound=tenant_a, sm=sm_a)
    dps = _run(event_loop, reader.list_data_points(
        tenant_context=_tenant_context(tenant_a), case_id=case.id))
    assert len(dps) == 2
    assert all(len(dp.assertions) == 1 for dp in dps)


# --- isolation scenarios ---


def test_save_case_isolated_per_tenant(event_loop, isolation_setup) -> None:
    tenant_a, _b, sm_a, sm_b = isolation_setup
    _seed_case(event_loop=event_loop, tenant_id=tenant_a, sm=sm_a)
    assert _row_count(event_loop, sm_a, cases_table) == 1
    assert _row_count(event_loop, sm_b, cases_table) == 0


def test_save_data_point_isolated_per_tenant(
    event_loop, isolation_setup
) -> None:
    tenant_a, _b, sm_a, sm_b = isolation_setup
    case = _seed_case(event_loop=event_loop, tenant_id=tenant_a, sm=sm_a)
    _seed_data_point(
        event_loop=event_loop, tenant_id=tenant_a, sm=sm_a, case_id=case.id)
    assert _row_count(event_loop, sm_a, assertions_table) == 1
    assert _row_count(event_loop, sm_b, assertions_table) == 0


def test_get_case_cross_tenant_returns_none(
    event_loop, isolation_setup
) -> None:
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    case = _seed_case(event_loop=event_loop, tenant_id=tenant_a, sm=sm_a)
    reader_for_b = _build_reader(bound=tenant_b, sm=sm_b)
    fetched = _run(event_loop, reader_for_b.get_case(
        tenant_context=_tenant_context(tenant_b), case_id=case.id))
    assert fetched is None


def test_list_cases_cross_tenant_returns_empty(
    event_loop, isolation_setup
) -> None:
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    _seed_case(event_loop=event_loop, tenant_id=tenant_a, sm=sm_a)
    reader_for_b = _build_reader(bound=tenant_b, sm=sm_b)
    page = _run(event_loop, reader_for_b.list_cases(
        tenant_context=_tenant_context(tenant_b),
        filters=None, cursor=None, page_size=20))
    assert page.cases == ()


def test_get_data_point_cross_tenant_returns_none(
    event_loop, isolation_setup
) -> None:
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    case = _seed_case(event_loop=event_loop, tenant_id=tenant_a, sm=sm_a)
    dp = _seed_data_point(
        event_loop=event_loop, tenant_id=tenant_a, sm=sm_a, case_id=case.id)
    reader_for_b = _build_reader(bound=tenant_b, sm=sm_b)
    fetched = _run(event_loop, reader_for_b.get_data_point(
        tenant_context=_tenant_context(tenant_b), data_point_id=dp.id))
    assert fetched is None


def test_adapter_rejects_tenant_context_mismatch(
    event_loop, isolation_setup
) -> None:
    """Defence-in-depth: TenantContext mismatch raises before session use."""
    tenant_a, tenant_b, sm_a, _sm_b = isolation_setup
    repo_for_a = _build_repo(bound=tenant_a, sm=sm_a)
    case = _make_case(tenant_id=tenant_a)
    with pytest.raises(ValueError, match="tenant"):
        _run(event_loop, repo_for_a.save_case(
            tenant_context=_tenant_context(tenant_b), case=case))
    assert _row_count(event_loop, sm_a, cases_table) == 0


def test_adapter_rejects_entity_tenant_mismatch(
    event_loop, isolation_setup
) -> None:
    """Second defence-in-depth: a Case carrying a foreign tenant_id is
    rejected even when the TenantContext matches the bound tenant."""
    tenant_a, tenant_b, sm_a, _sm_b = isolation_setup
    repo_for_a = _build_repo(bound=tenant_a, sm=sm_a)
    foreign_case = _make_case(tenant_id=tenant_b)
    with pytest.raises(ValueError, match="tenant"):
        _run(event_loop, repo_for_a.save_case(
            tenant_context=_tenant_context(tenant_a), case=foreign_case))
    assert _row_count(event_loop, sm_a, cases_table) == 0


# --------------------------------------------------------------------
# Structural isolation: the migration is deployed to the real per-tenant
# containers. The S43-commit-5 deferral resolves here at S43b — 0016 is
# applied to tenant_a and tenant_b, and absent from the control plane
# (portfolio data is per-tenant per D32).
# --------------------------------------------------------------------

_PORTFOLIO_TABLES = ("assertions", "cases", "data_points")


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
    in_clause = ", ".join(f"'{t}'" for t in _PORTFOLIO_TABLES)
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
def test_per_tenant_db_has_all_three_portfolio_tables(
    compose_running: None, service: str, user_env: str, db_env: str
) -> None:
    """D32 / D124: each tenant's DB carries the three portfolio tables."""
    found = set(
        _exec_psql(
            service, _env(user_env), _env(db_env), _table_list_query()
        ).splitlines()
    )
    assert found == set(_PORTFOLIO_TABLES), (
        f"per-tenant DB {service} missing portfolio tables; "
        f"found {sorted(found)}"
    )


def test_control_plane_db_has_no_portfolio_tables(
    compose_running: None,
) -> None:
    """D32 / D124: the control plane carries no portfolio tables."""
    found = _exec_psql(
        "postgres-control-plane",
        _env("POSTGRES_CONTROL_PLANE_USER"),
        _env("POSTGRES_CONTROL_PLANE_DB"),
        _table_list_query(),
    )
    assert found == "", (
        f"control-plane should have no portfolio tables; "
        f"psql reported {found!r}"
    )
