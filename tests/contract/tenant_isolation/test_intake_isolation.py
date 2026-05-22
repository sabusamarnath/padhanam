"""Tenant isolation contract tests for the intake context (D24, D32, D127).

Per D32, per-tenant data planes are independent Postgres instances.
Per D127, the ``intakes`` table lives on each tenant's database.

Behavioural cross-tenant isolation plus adapter round-trips: intakes
persisted via the Postgres adapter land on the owning tenant's DB
only; cross-tenant reads return None / empty; the defence-in-depth
ValueError fires on TenantContext or entity tenant_id mismatch.
Round-trip, ordering, cursor-pagination, and source-filter
scenarios exercise the repository.

The synthetic dual-tenant fixture provisions two databases on the
loopback control-plane Postgres and applies the per-tenant Alembic
chain (head includes 0017) to each. The structural "migration
deployed to the real per-tenant containers" check lands with the
S44b live-stack smoke.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from contexts.intake.adapters.outbound.postgres._tables import (
    intakes as intakes_table,
)
from contexts.intake.adapters.outbound.postgres.intake_repository import (
    PostgresIntakeRepository,
)
from contexts.intake.domain import (
    IntakeRecord,
    IntakeSource,
    ManualEntryPayload,
)
from contexts.intake.domain.query_filters import (
    IntakeListCursor,
    IntakeListFilters,
)
from padhanam.config import ControlPlaneSettings
from shared_kernel import ActorReference, TenantContext, TenantId

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
    """Provision two synthetic per-tenant databases, apply the
    per-tenant Alembic chain, and yield (tenant_a, tenant_b, sm_a, sm_b)."""
    settings = _cp_settings()
    suffix = uuid.uuid4().hex[:8]
    tenant_a_db = f"intk_iso_a_{suffix}"
    tenant_b_db = f"intk_iso_b_{suffix}"
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


def _row_count(event_loop, sm) -> int:
    async def run() -> int:
        async with sm() as session:
            return (
                await session.execute(
                    sa.select(sa.func.count()).select_from(intakes_table)
                )
            ).scalar() or 0
    return event_loop.run_until_complete(run())


def _tenant_context(tenant_id: uuid.UUID) -> TenantContext:
    return TenantContext(
        tenant_id=str(tenant_id),
        jurisdiction="eu-west",
        cost_attribution_id=str(tenant_id),
    )


def _build_repo(*, bound: uuid.UUID, sm) -> PostgresIntakeRepository:
    async def resolver(_tid: TenantId):
        return sm
    return PostgresIntakeRepository(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=TenantId(str(bound)),
    )


_BASE_TS = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_intake(
    *, tenant_id: uuid.UUID, created_at: datetime | None = None,
    raw_text: str = "iso intake",
) -> IntakeRecord:
    return IntakeRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        intake_source=IntakeSource.MANUAL_ENTRY,
        payload=ManualEntryPayload(raw_text=raw_text),
        authored_by=_ACTOR,
        created_at=created_at or _BASE_TS,
    )


def _seed(*, event_loop, tenant_id, sm, **kw) -> IntakeRecord:
    intake = _make_intake(tenant_id=tenant_id, **kw)
    repo = _build_repo(bound=tenant_id, sm=sm)
    _run(event_loop, repo.save(
        tenant_context=_tenant_context(tenant_id), intake=intake))
    return intake


# --- round-trip scenarios ---


def test_save_and_get_intake_round_trip(event_loop, isolation_setup) -> None:
    tenant_a, _tb, sm_a, _sm_b = isolation_setup
    intake = _seed(
        event_loop=event_loop, tenant_id=tenant_a, sm=sm_a,
        raw_text="round-trip text",
    )
    repo = _build_repo(bound=tenant_a, sm=sm_a)
    fetched = _run(event_loop, repo.get_by_id(
        tenant_context=_tenant_context(tenant_a), intake_id=intake.id))
    assert fetched is not None
    assert fetched.id == intake.id
    assert fetched.intake_source is IntakeSource.MANUAL_ENTRY
    assert fetched.payload.raw_text == "round-trip text"
    assert fetched.authored_by.user_id == "iso-test"


def test_get_intake_absent_returns_none(event_loop, isolation_setup) -> None:
    tenant_a, _tb, sm_a, _sm_b = isolation_setup
    repo = _build_repo(bound=tenant_a, sm=sm_a)
    fetched = _run(event_loop, repo.get_by_id(
        tenant_context=_tenant_context(tenant_a), intake_id=uuid4()))
    assert fetched is None


def test_payload_round_trip_preserves_optional_fields(
    event_loop, isolation_setup
) -> None:
    tenant_a, _tb, sm_a, _sm_b = isolation_setup
    cid = uuid4()
    intake = IntakeRecord(
        id=uuid4(), tenant_id=tenant_a, jurisdiction="eu-west",
        intake_source=IntakeSource.MANUAL_ENTRY,
        payload=ManualEntryPayload(
            raw_text="with hints", intent_hint="create-case",
            linked_case_ids=(cid,),
        ),
        authored_by=_ACTOR, created_at=_BASE_TS,
    )
    repo = _build_repo(bound=tenant_a, sm=sm_a)
    _run(event_loop, repo.save(
        tenant_context=_tenant_context(tenant_a), intake=intake))
    fetched = _run(event_loop, repo.get_by_id(
        tenant_context=_tenant_context(tenant_a), intake_id=intake.id))
    assert fetched is not None
    assert fetched.payload.intent_hint == "create-case"
    assert fetched.payload.linked_case_ids == (cid,)


def test_list_intakes_returns_tenant_intakes(
    event_loop, isolation_setup
) -> None:
    tenant_a, _tb, sm_a, _sm_b = isolation_setup
    for i in range(3):
        _seed(
            event_loop=event_loop, tenant_id=tenant_a, sm=sm_a,
            created_at=_BASE_TS + timedelta(hours=i), raw_text=f"intake {i}",
        )
    repo = _build_repo(bound=tenant_a, sm=sm_a)
    page = _run(event_loop, repo.list_for_tenant(
        tenant_context=_tenant_context(tenant_a),
        filters=None, cursor=None, page_size=10))
    assert len(page.intakes) == 3
    assert page.next_cursor is None
    # newest first
    assert page.intakes[0].payload.raw_text == "intake 2"


def test_list_intakes_cursor_pagination(event_loop, isolation_setup) -> None:
    tenant_a, _tb, sm_a, _sm_b = isolation_setup
    for i in range(3):
        _seed(
            event_loop=event_loop, tenant_id=tenant_a, sm=sm_a,
            created_at=_BASE_TS + timedelta(hours=i),
        )
    repo = _build_repo(bound=tenant_a, sm=sm_a)
    page1 = _run(event_loop, repo.list_for_tenant(
        tenant_context=_tenant_context(tenant_a),
        filters=None, cursor=None, page_size=2))
    assert len(page1.intakes) == 2
    assert page1.next_cursor is not None
    page2 = _run(event_loop, repo.list_for_tenant(
        tenant_context=_tenant_context(tenant_a),
        filters=None, cursor=page1.next_cursor, page_size=2))
    assert len(page2.intakes) == 1
    assert page2.next_cursor is None


def test_list_intakes_source_filter(event_loop, isolation_setup) -> None:
    tenant_a, _tb, sm_a, _sm_b = isolation_setup
    _seed(event_loop=event_loop, tenant_id=tenant_a, sm=sm_a)
    repo = _build_repo(bound=tenant_a, sm=sm_a)
    page = _run(event_loop, repo.list_for_tenant(
        tenant_context=_tenant_context(tenant_a),
        filters=IntakeListFilters(
            intake_sources=(IntakeSource.MANUAL_ENTRY,)
        ),
        cursor=None, page_size=10))
    assert len(page.intakes) == 1


# --- cross-tenant isolation ---


def test_save_intake_isolated_per_tenant(event_loop, isolation_setup) -> None:
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    _seed(event_loop=event_loop, tenant_id=tenant_a, sm=sm_a)
    assert _row_count(event_loop, sm_a) == 1
    assert _row_count(event_loop, sm_b) == 0


def test_get_intake_cross_tenant_returns_none(
    event_loop, isolation_setup
) -> None:
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    intake = _seed(event_loop=event_loop, tenant_id=tenant_a, sm=sm_a)
    repo_b = _build_repo(bound=tenant_b, sm=sm_b)
    fetched = _run(event_loop, repo_b.get_by_id(
        tenant_context=_tenant_context(tenant_b), intake_id=intake.id))
    assert fetched is None


def test_list_intakes_cross_tenant_returns_empty(
    event_loop, isolation_setup
) -> None:
    tenant_a, tenant_b, sm_a, sm_b = isolation_setup
    _seed(event_loop=event_loop, tenant_id=tenant_a, sm=sm_a)
    repo_b = _build_repo(bound=tenant_b, sm=sm_b)
    page = _run(event_loop, repo_b.list_for_tenant(
        tenant_context=_tenant_context(tenant_b),
        filters=None, cursor=None, page_size=10))
    assert page.intakes == ()


def test_adapter_rejects_tenant_context_mismatch(
    event_loop, isolation_setup
) -> None:
    tenant_a, tenant_b, sm_a, _sm_b = isolation_setup
    repo = _build_repo(bound=tenant_a, sm=sm_a)
    intake = _make_intake(tenant_id=tenant_a)
    with pytest.raises(ValueError, match="defence-in-depth"):
        _run(event_loop, repo.save(
            tenant_context=_tenant_context(tenant_b), intake=intake))


def test_adapter_rejects_entity_tenant_mismatch(
    event_loop, isolation_setup
) -> None:
    tenant_a, tenant_b, sm_a, _sm_b = isolation_setup
    repo = _build_repo(bound=tenant_a, sm=sm_a)
    foreign = _make_intake(tenant_id=tenant_b)
    with pytest.raises(ValueError, match="does not match"):
        _run(event_loop, repo.save(
            tenant_context=_tenant_context(tenant_a), intake=foreign))
