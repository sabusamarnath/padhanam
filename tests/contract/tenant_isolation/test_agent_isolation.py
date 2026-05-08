"""Tenant isolation contract tests for the agent context (D32 / D75).

Per D32, per-tenant data planes are independent Postgres instances.
Per D75, the agent context is per-tenant-scoped: the two agent
tables live on each tenant's database, NOT on the control-plane.
This contrasts with the methodology context's inverted shape (S23 /
D74) where templates live on control-plane only.

Two layers:

1. Structural isolation (mirrors ingestion isolation pattern at
   tests/contract/tenant_isolation/test_ingestion_isolation.py):
   each tenant's DB carries the two agent tables; the control-plane
   DB does not. Asserted by shelling out to docker compose exec
   and querying information_schema.tables.

2. Behavioural cross-tenant isolation: the AgentPostgresRepository
   with a per-tenant resolver isolates writes and reads between
   tenants. Same synthetic-database pattern the audit isolation
   tests use (because per-tenant Postgres instances do not bind
   host ports per S5). Provisions two synthetic per-tenant
   databases on the loopback control-plane Postgres; the resolver
   maps each test tenant_id to its sessionmaker; cross-tenant
   reads return not-found and writes go to the routed database
   only.
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
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from contexts.agent.adapters.outbound.postgres import (
    AgentPostgresRepository,
    agent_revisions,
    agent_templates,
)
from contexts.agent.domain.agent import AgentRevision, AgentTemplate
from padhanam.config import ControlPlaneSettings
from padhanam.observability.security_events import SecurityEvent
from shared_kernel import TenantContext, TenantId


_AGENT_TABLES = (
    "agent_revisions",
    "agent_templates",
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
    in_clause = ", ".join(f"'{t}'" for t in _AGENT_TABLES)
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
def test_per_tenant_db_has_both_agent_tables(
    compose_running: None,
    service: str,
    user_env: str,
    db_env: str,
) -> None:
    """D32 / D75 positive case: each tenant's DB has both agent tables."""
    user = _env(user_env)
    db = _env(db_env)
    found = set(_exec_psql(service, user, db, _table_list_query()).splitlines())
    assert found == set(_AGENT_TABLES), (
        f"per-tenant DB {service} missing agent tables; found {sorted(found)}"
    )


def test_control_plane_db_has_no_agent_tables(compose_running: None) -> None:
    """D32 / D75 negative case: control-plane DB has neither agent table.

    Contrast with methodology_templates and methodology_revisions
    which DO live on control-plane per D33 / D74. The agent context
    is per-tenant-scoped; agent data must not leak onto control-
    plane.
    """
    user = _env("POSTGRES_CONTROL_PLANE_USER")
    db = _env("POSTGRES_CONTROL_PLANE_DB")
    found = _exec_psql(
        "postgres-control-plane", user, db, _table_list_query()
    )
    assert found == "", (
        f"control-plane should have no agent tables; psql reported {found!r}"
    )


@pytest.mark.parametrize(
    "service,user_env,db_env",
    [
        ("postgres-tenant-a", "POSTGRES_TENANT_A_USER", "POSTGRES_TENANT_A_DB"),
        ("postgres-tenant-b", "POSTGRES_TENANT_B_USER", "POSTGRES_TENANT_B_DB"),
    ],
)
def test_per_tenant_db_has_lineage_check_constraint(
    compose_running: None,
    service: str,
    user_env: str,
    db_env: str,
) -> None:
    """D75 paired-NULL invariant: each tenant DB carries the
    agent_templates_lineage_paired_null CHECK constraint."""
    user = _env(user_env)
    db = _env(db_env)
    query = (
        "SELECT conname FROM pg_constraint "
        "WHERE conname='agent_templates_lineage_paired_null'"
    )
    found = _exec_psql(service, user, db, query)
    assert found == "agent_templates_lineage_paired_null", (
        f"CHECK constraint missing on {service}; found {found!r}"
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


class _CollectingSecurityEvents:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def emit(self, event: SecurityEvent) -> None:
        self.events.append(event)


def _make_template(name: str = "iso-test") -> AgentTemplate:
    return AgentTemplate(
        id=uuid4(),
        name=name,
        description="Isolation contract fixture",
        created_by_user_id="alice",
        created_at=datetime.now(timezone.utc),
    )


def _make_revision(*, template_id: UUID) -> AgentRevision:
    return AgentRevision(
        id=uuid4(),
        agent_template_id=template_id,
        version=1,
        system_prompt="prompt",
        source_ids=(),
        tool_allowlist=(),
        retrieval_strategy={"strategy": "vector_only", "params": {}},
        filter_tree={"node": {}},
        top_k=5,
        min_score=Decimal("0.7"),
        model_selection="qwen2.5:7b",
        created_by_user_id="alice",
        created_at=datetime.now(timezone.utc),
        previous_revision_hash="0" * 64,
        this_revision_hash="abc",
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
    each, and yield (repo, tenant_a_ctx, tenant_b_ctx, sm_a, sm_b)."""
    settings = _cp_settings()
    suffix = uuid.uuid4().hex[:8]
    tenant_a_db = f"agent_iso_a_{suffix}"
    tenant_b_db = f"agent_iso_b_{suffix}"
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

    sm_by_id = {tenant_a_uuid: sm_a, tenant_b_uuid: sm_b}

    async def resolver(tenant_id: TenantId) -> async_sessionmaker[AsyncSession]:
        sm = sm_by_id.get(str(tenant_id))
        if sm is None:
            raise LookupError(f"unexpected tenant_id {tenant_id!r}")
        return sm

    sec = _CollectingSecurityEvents()
    repo = AgentPostgresRepository(
        per_tenant_sessionmaker_resolver=resolver,
        security_events=sec,
    )

    ctx_a = TenantContext(
        tenant_id=tenant_a_uuid, jurisdiction="eu-west",
        cost_attribution_id=tenant_a_uuid,
    )
    ctx_b = TenantContext(
        tenant_id=tenant_b_uuid, jurisdiction="eu-west",
        cost_attribution_id=tenant_b_uuid,
    )

    try:
        yield repo, ctx_a, ctx_b, sm_a, sm_b
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
                    sa.select(sa.func.count()).select_from(agent_templates)
                )
            ).scalar() or 0
    return event_loop.run_until_complete(run())


def test_tenant_a_create_isolated_to_tenant_a_database(
    event_loop, isolation_setup
) -> None:
    """Cross-tenant write isolation: a tenant-A create lands on tenant-A's
    DB only; tenant-B's DB stays empty."""
    repo, ctx_a, ctx_b, sm_a, sm_b = isolation_setup

    template = _make_template(name="A-only")
    revision = _make_revision(template_id=template.id)
    event_loop.run_until_complete(
        repo.create_template(template, revision, ctx_a)
    )

    assert _row_count(event_loop, sm_a) == 1
    assert _row_count(event_loop, sm_b) == 0


def test_tenant_b_create_isolated_from_tenant_a(
    event_loop, isolation_setup
) -> None:
    """Cross-tenant write isolation: a tenant-B create lands on tenant-B's
    DB only; tenant-A's DB unaffected."""
    repo, ctx_a, ctx_b, sm_a, sm_b = isolation_setup

    template = _make_template(name="B-only")
    revision = _make_revision(template_id=template.id)
    event_loop.run_until_complete(
        repo.create_template(template, revision, ctx_b)
    )

    assert _row_count(event_loop, sm_a) == 0
    assert _row_count(event_loop, sm_b) == 1


def test_cross_tenant_read_returns_not_found(
    event_loop, isolation_setup
) -> None:
    """Cross-tenant read isolation: tenant-A creates, tenant-B reads with
    the same id, gets LookupError because the row doesn't exist on
    tenant-B's DB."""
    repo, ctx_a, ctx_b, _, _ = isolation_setup

    template = _make_template(name="A-secret")
    revision = _make_revision(template_id=template.id)
    event_loop.run_until_complete(
        repo.create_template(template, revision, ctx_a)
    )

    # Tenant A can read it.
    fetched, _ = event_loop.run_until_complete(
        repo.get_template(template.id, ctx_a)
    )
    assert fetched.id == template.id

    # Tenant B cannot read it (the row does not exist on tenant-B's DB).
    with pytest.raises(LookupError):
        event_loop.run_until_complete(
            repo.get_template(template.id, ctx_b)
        )


def test_chains_advance_independently_per_tenant(
    event_loop, isolation_setup
) -> None:
    """Each tenant's hash-chain advances independently; cross-tenant
    revisions do not influence each other."""
    repo, ctx_a, ctx_b, _, _ = isolation_setup

    template_a = _make_template(name="ChainA")
    revision_a = _make_revision(template_id=template_a.id)
    event_loop.run_until_complete(
        repo.create_template(template_a, revision_a, ctx_a)
    )

    template_b = _make_template(name="ChainB")
    revision_b = _make_revision(template_id=template_b.id)
    event_loop.run_until_complete(
        repo.create_template(template_b, revision_b, ctx_b)
    )

    # Tenant A's template is not visible in tenant B's list, and vice versa.
    listed_a = event_loop.run_until_complete(repo.list_templates(ctx_a))
    listed_b = event_loop.run_until_complete(repo.list_templates(ctx_b))
    a_ids = {t.id for t in listed_a}
    b_ids = {t.id for t in listed_b}
    assert template_a.id in a_ids
    assert template_a.id not in b_ids
    assert template_b.id in b_ids
    assert template_b.id not in a_ids
