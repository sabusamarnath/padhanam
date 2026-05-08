"""Integration tests for AgentPostgresRepository against a per-tenant data plane (D75).

The test fixture provisions a synthetic database on the loopback-bound
control-plane Postgres instance and applies the per-tenant Alembic
chain to it (the same loopback exception that the audit isolation
tests use because per-tenant Postgres instances do not bind host
ports per S5). The AgentPostgresRepository is then exercised against
this synthetic per-tenant database with a resolver that maps the test
tenant_id to its sessionmaker.

Behaviour scaffolds promoted from the port contract tests at
``tests/unit/contexts/agent/ports/test_agent_repository_port_contract.py``
land here as live assertions.
"""

from __future__ import annotations

import asyncio
import os
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
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
)
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


def _make_template(
    *,
    name: str = "TestAgent",
    description: str | None = "Integration test fixture",
    source_methodology_template_id: UUID | None = None,
    source_methodology_template_version: int | None = None,
) -> AgentTemplate:
    return AgentTemplate(
        id=uuid4(),
        name=name,
        description=description,
        source_methodology_template_id=source_methodology_template_id,
        source_methodology_template_version=source_methodology_template_version,
        created_by_user_id="alice",
        created_at=datetime.now(timezone.utc),
    )


def _make_revision(
    *,
    template_id: UUID,
    version: int,
    previous_hash: str = "0" * 64,
    this_hash: str = "abc",
    min_score: Decimal = Decimal("0.7"),
    system_prompt: str = "v1 prompt",
) -> AgentRevision:
    return AgentRevision(
        id=uuid4(),
        agent_template_id=template_id,
        version=version,
        system_prompt=system_prompt,
        source_ids=(),
        tool_allowlist=(),
        retrieval_strategy={"strategy": "vector_only", "params": {}},
        filter_tree={"node": {}},
        top_k=5,
        min_score=min_score,
        model_selection="qwen2.5:7b",
        created_by_user_id="alice",
        created_at=datetime.now(timezone.utc),
        previous_revision_hash=previous_hash,
        this_revision_hash=this_hash,
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
def repo(event_loop):
    """Provision a synthetic per-tenant database, apply the per-tenant
    Alembic chain to it, and yield (repo, security_events_collector,
    tenant_context). Teardown drops the database.
    """
    settings = _cp_settings()
    suffix = uuid.uuid4().hex[:8]
    tenant_db = f"agent_test_{suffix}"
    tenant_uuid = "00000000-0000-4000-8000-" + suffix.rjust(11, "0") + "a"

    sync_engine = sa.create_engine(
        _sync_url(settings), isolation_level="AUTOCOMMIT"
    )
    try:
        with sync_engine.connect() as conn:
            conn.execute(sa.text(f'CREATE DATABASE "{tenant_db}"'))
    except Exception as e:
        sync_engine.dispose()
        pytest.skip(f"control-plane Postgres unreachable: {e}")

    cfg = Config("alembic.ini", ini_section="tenant")
    cfg.set_main_option("sqlalchemy.url", _sync_url(settings, tenant_db))
    command.upgrade(cfg, "head")

    tenant_engine = create_async_engine(_async_url(settings, tenant_db))
    tenant_sm = async_sessionmaker(tenant_engine, expire_on_commit=False)

    async def resolver(tid: TenantId) -> async_sessionmaker[AsyncSession]:
        if str(tid) != tenant_uuid:
            raise LookupError(f"unexpected tenant_id {tid!r}")
        return tenant_sm

    sec = _CollectingSecurityEvents()
    repository = AgentPostgresRepository(
        per_tenant_sessionmaker_resolver=resolver,
        security_events=sec,
    )
    tenant_context = TenantContext(
        tenant_id=tenant_uuid,
        jurisdiction="eu-west",
        cost_attribution_id=tenant_uuid,
    )

    try:
        yield repository, sec, tenant_context
    finally:
        async def cleanup() -> None:
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


def test_create_template_persists_template_and_initial_revision_atomically(
    event_loop, repo
) -> None:
    r, sec, ctx = repo
    template = _make_template()
    revision = _make_revision(template_id=template.id, version=1)
    event_loop.run_until_complete(r.create_template(template, revision, ctx))

    fetched_template, fetched_revision = event_loop.run_until_complete(
        r.get_template(template.id, ctx)
    )
    assert fetched_template.id == template.id
    assert fetched_template.name == template.name
    assert fetched_template.source_methodology_template_id is None
    assert fetched_template.source_methodology_template_version is None
    assert fetched_revision.version == 1
    assert fetched_revision.this_revision_hash == revision.this_revision_hash

    assert any(
        e.category is SecurityEventCategory.PRIVILEGED_ACTION
        and e.action == "agent.create_template"
        for e in sec.events
    )


def test_create_template_with_methodology_lineage_populated(event_loop, repo) -> None:
    r, _, ctx = repo
    methodology_id = uuid4()
    template = _make_template(
        source_methodology_template_id=methodology_id,
        source_methodology_template_version=2,
    )
    revision = _make_revision(template_id=template.id, version=1)
    event_loop.run_until_complete(r.create_template(template, revision, ctx))

    fetched, _ = event_loop.run_until_complete(r.get_template(template.id, ctx))
    assert fetched.source_methodology_template_id == methodology_id
    assert fetched.source_methodology_template_version == 2


def test_add_revision_increments_version_and_chains_hash(event_loop, repo) -> None:
    r, sec, ctx = repo
    template = _make_template(name="ChainTest")
    revision1 = _make_revision(
        template_id=template.id, version=1, this_hash="hash_v1"
    )
    event_loop.run_until_complete(r.create_template(template, revision1, ctx))

    revision2 = _make_revision(
        template_id=template.id,
        version=2,
        previous_hash=revision1.this_revision_hash,
        this_hash="hash_v2",
        min_score=Decimal("0.85"),
        system_prompt="v2 prompt",
    )
    event_loop.run_until_complete(r.add_revision(template.id, revision2, ctx))

    _, fetched_v2 = event_loop.run_until_complete(
        r.get_template(template.id, ctx, version=2)
    )
    assert fetched_v2.previous_revision_hash == revision1.this_revision_hash
    assert fetched_v2.this_revision_hash == "hash_v2"
    assert fetched_v2.version == 2

    assert any(e.action == "agent.add_revision" for e in sec.events)


def test_get_template_returns_latest_revision_when_version_omitted(
    event_loop, repo
) -> None:
    r, _, ctx = repo
    template = _make_template(name="LatestTest")
    rev1 = _make_revision(template_id=template.id, version=1, this_hash="h1")
    event_loop.run_until_complete(r.create_template(template, rev1, ctx))

    rev2 = _make_revision(
        template_id=template.id, version=2, previous_hash="h1", this_hash="h2"
    )
    event_loop.run_until_complete(r.add_revision(template.id, rev2, ctx))

    rev3 = _make_revision(
        template_id=template.id, version=3, previous_hash="h2", this_hash="h3"
    )
    event_loop.run_until_complete(r.add_revision(template.id, rev3, ctx))

    _, latest = event_loop.run_until_complete(r.get_template(template.id, ctx))
    assert latest.version == 3


def test_archive_template_marks_archived_at_and_leaves_revisions_intact(
    event_loop, repo
) -> None:
    r, sec, ctx = repo
    template = _make_template(name="ArchiveTest")
    revision = _make_revision(template_id=template.id, version=1)
    event_loop.run_until_complete(r.create_template(template, revision, ctx))

    archived = event_loop.run_until_complete(
        r.archive_template(template.id, ctx)
    )
    assert archived.archived_at is not None

    _, rev = event_loop.run_until_complete(
        r.get_template(template.id, ctx, version=1)
    )
    assert rev.version == 1
    assert rev.this_revision_hash == revision.this_revision_hash

    assert any(e.action == "agent.archive_template" for e in sec.events)


def test_list_templates_excludes_archived_by_default(event_loop, repo) -> None:
    r, _, ctx = repo
    active = _make_template(name="ActiveAgent")
    active_rev = _make_revision(template_id=active.id, version=1)
    event_loop.run_until_complete(r.create_template(active, active_rev, ctx))

    archived = _make_template(name="ArchivedAgent")
    archived_rev = _make_revision(template_id=archived.id, version=1)
    event_loop.run_until_complete(
        r.create_template(archived, archived_rev, ctx)
    )
    event_loop.run_until_complete(r.archive_template(archived.id, ctx))

    listed = event_loop.run_until_complete(r.list_templates(ctx))
    listed_ids = {t.id for t in listed}
    assert active.id in listed_ids
    assert archived.id not in listed_ids


def test_list_templates_include_archived_returns_all(event_loop, repo) -> None:
    r, _, ctx = repo
    active = _make_template(name="ActiveAgent")
    active_rev = _make_revision(template_id=active.id, version=1)
    event_loop.run_until_complete(r.create_template(active, active_rev, ctx))

    archived = _make_template(name="ArchivedAgent")
    archived_rev = _make_revision(template_id=archived.id, version=1)
    event_loop.run_until_complete(
        r.create_template(archived, archived_rev, ctx)
    )
    event_loop.run_until_complete(r.archive_template(archived.id, ctx))

    listed = event_loop.run_until_complete(
        r.list_templates(ctx, include_archived=True)
    )
    listed_ids = {t.id for t in listed}
    assert active.id in listed_ids
    assert archived.id in listed_ids


def test_partial_unique_index_allows_archived_name_reuse(
    event_loop, repo
) -> None:
    """Archived templates retain their name without conflict (D31)."""
    r, _, ctx = repo
    t1 = _make_template(name="ReuseTest")
    rev1 = _make_revision(template_id=t1.id, version=1)
    event_loop.run_until_complete(r.create_template(t1, rev1, ctx))
    event_loop.run_until_complete(r.archive_template(t1.id, ctx))

    t2 = _make_template(name="ReuseTest")
    rev2 = _make_revision(template_id=t2.id, version=1)
    event_loop.run_until_complete(r.create_template(t2, rev2, ctx))


def test_partial_unique_index_blocks_active_name_collision(
    event_loop, repo
) -> None:
    r, _, ctx = repo
    t1 = _make_template(name="CollisionTest")
    rev1 = _make_revision(template_id=t1.id, version=1)
    event_loop.run_until_complete(r.create_template(t1, rev1, ctx))

    t2 = _make_template(name="CollisionTest")
    rev2 = _make_revision(template_id=t2.id, version=1)
    with pytest.raises(Exception):
        event_loop.run_until_complete(r.create_template(t2, rev2, ctx))


def test_unique_template_version_constraint_blocks_duplicate_version(
    event_loop, repo
) -> None:
    r, _, ctx = repo
    template = _make_template(name="DupVersionTest")
    rev1 = _make_revision(template_id=template.id, version=1)
    event_loop.run_until_complete(r.create_template(template, rev1, ctx))

    rev1_dup = _make_revision(template_id=template.id, version=1)
    with pytest.raises(Exception):
        event_loop.run_until_complete(r.add_revision(template.id, rev1_dup, ctx))


def test_get_template_raises_for_unknown_id(event_loop, repo) -> None:
    r, _, ctx = repo
    unknown_id = uuid4()
    with pytest.raises(LookupError):
        event_loop.run_until_complete(r.get_template(unknown_id, ctx))


def test_get_template_raises_for_unknown_version(event_loop, repo) -> None:
    r, _, ctx = repo
    template = _make_template(name="UnknownVersion")
    revision = _make_revision(template_id=template.id, version=1)
    event_loop.run_until_complete(r.create_template(template, revision, ctx))

    with pytest.raises(LookupError):
        event_loop.run_until_complete(
            r.get_template(template.id, ctx, version=99)
        )
