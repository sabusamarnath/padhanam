"""Integration tests for ToolPostgresRepository (D89).

Skip gracefully when control-plane Postgres is unreachable; preserve
migration-owned rows (the retrieval tool from
``0009_create_tools_tables``) by scoping truncation to non-migration
actors.

Covers commit 2's port surface:
- create_template persists template + initial revision atomically
- get_template / find_revision / list_templates round-trip
- archive_template marks archived_at
- verify_chain_integrity passes for honest chains
- verify_chain_integrity raises on tamper

The hash-chain tamper case is the load-bearing D26 audit assertion:
edit the persisted ``description`` field on a tool template (which
spans the revision hash payload per D89 / D74's chain-self-containment
pattern) and confirm verify_chain_integrity surfaces the divergence.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa

from contexts.tools.adapters.outbound.postgres.tool_repository import (
    ToolPostgresRepository,
    tool_revisions,
    tools,
)
from contexts.tools.domain.exceptions import ToolNotFoundError
from contexts.tools.domain.tool import (
    Classification,
    Tool,
    ToolRevision,
)
from padhanam.config import ControlPlaneSettings
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
)
from padhanam.security.hash_chain import (
    GENESIS_REVISION_HASH,
    compute_revision_hash,
)


def _make_template(
    name: str = "TestTool",
    classification: Classification = Classification.READ_ONLY,
) -> Tool:
    return Tool(
        id=uuid4(),
        name=name,
        description="Integration test tool fixture",
        classification=classification,
        created_by_user_id="alice",
        created_at=datetime.now(timezone.utc),
    )


def _content_payload(
    *,
    name: str,
    description: str | None,
    classification: Classification,
    parameters_schema: dict,
    returns_schema: dict,
) -> dict:
    return {
        "name": name,
        "description": description,
        "classification": classification.value,
        "parameters_schema": parameters_schema,
        "returns_schema": returns_schema,
    }


def _make_revision(
    *,
    template: Tool,
    version: int,
    previous_hash: str,
    parameters_schema: dict | None = None,
    returns_schema: dict | None = None,
) -> ToolRevision:
    params = parameters_schema if parameters_schema is not None else {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }
    returns = returns_schema if returns_schema is not None else {
        "type": "string",
    }
    payload = _content_payload(
        name=template.name,
        description=template.description,
        classification=template.classification,
        parameters_schema=params,
        returns_schema=returns,
    )
    this_hash = compute_revision_hash(
        content_payload=payload, previous_hash=previous_hash
    )
    return ToolRevision(
        id=uuid4(),
        tool_id=template.id,
        version=version,
        parameters_schema=params,
        returns_schema=returns,
        bc_result={},
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
def repo(
    event_loop: asyncio.AbstractEventLoop,
) -> Iterator[tuple[ToolPostgresRepository, _CollectingSecurityEvents]]:
    base = ControlPlaneSettings()
    settings = ControlPlaneSettings(
        user=base.user,
        password=base.password,
        db=base.db,
        host=os.environ.get("CONTROL_PLANE_HOST_OVERRIDE", "127.0.0.1"),
        port=int(os.environ.get("CONTROL_PLANE_PORT_OVERRIDE", "5433")),
    )
    sec = _CollectingSecurityEvents()
    r = ToolPostgresRepository.from_settings(
        settings=settings, security_events=sec
    )

    async def setup() -> None:
        async with r._sessionmaker() as session:
            await session.execute(
                sa.delete(tool_revisions).where(
                    tool_revisions.c.created_by_user_id.notlike("migration:%")
                )
            )
            await session.execute(
                sa.delete(tools).where(
                    tools.c.created_by_user_id.notlike("migration:%")
                )
            )
            await session.commit()

    try:
        event_loop.run_until_complete(setup())
    except Exception as e:
        event_loop.run_until_complete(r.dispose())
        pytest.skip(f"control-plane Postgres unreachable: {e}")
    try:
        yield r, sec
    finally:
        async def teardown() -> None:
            async with r._sessionmaker() as session:
                await session.execute(
                    sa.delete(tool_revisions).where(
                        tool_revisions.c.created_by_user_id.notlike(
                            "migration:%"
                        )
                    )
                )
                await session.execute(
                    sa.delete(tools).where(
                        tools.c.created_by_user_id.notlike("migration:%")
                    )
                )
                await session.commit()
            await r.dispose()

        event_loop.run_until_complete(teardown())


def test_create_template_persists_atomically(event_loop, repo) -> None:
    r, sec = repo
    t = _make_template()
    rev = _make_revision(template=t, version=1, previous_hash=GENESIS_REVISION_HASH)
    event_loop.run_until_complete(r.create_template(t, rev))

    fetched_t, fetched_r = event_loop.run_until_complete(r.get_template(t.id))
    assert fetched_t.id == t.id
    assert fetched_t.classification is Classification.READ_ONLY
    assert fetched_r.version == 1
    assert fetched_r.previous_revision_hash == GENESIS_REVISION_HASH
    assert fetched_r.this_revision_hash == rev.this_revision_hash

    assert any(
        e.category is SecurityEventCategory.PRIVILEGED_ACTION
        and e.action == "tool.create_template"
        for e in sec.events
    )


def test_find_revision_returns_template_and_revision(event_loop, repo) -> None:
    r, _ = repo
    t = _make_template()
    rev = _make_revision(template=t, version=1, previous_hash=GENESIS_REVISION_HASH)
    event_loop.run_until_complete(r.create_template(t, rev))

    found_t, found_r = event_loop.run_until_complete(r.find_revision(rev.id))
    assert found_t.id == t.id
    assert found_r.id == rev.id


def test_archive_template_marks_archived_at(event_loop, repo) -> None:
    r, _ = repo
    t = _make_template()
    rev = _make_revision(template=t, version=1, previous_hash=GENESIS_REVISION_HASH)
    event_loop.run_until_complete(r.create_template(t, rev))

    archived = event_loop.run_until_complete(r.archive_template(t.id))
    assert archived.archived_at is not None


def test_list_templates_excludes_archived(event_loop, repo) -> None:
    r, _ = repo
    t1 = _make_template(name="alpha-tool")
    rev1 = _make_revision(template=t1, version=1, previous_hash=GENESIS_REVISION_HASH)
    t2 = _make_template(name="beta-tool")
    rev2 = _make_revision(template=t2, version=1, previous_hash=GENESIS_REVISION_HASH)
    event_loop.run_until_complete(r.create_template(t1, rev1))
    event_loop.run_until_complete(r.create_template(t2, rev2))
    event_loop.run_until_complete(r.archive_template(t1.id))

    listed = event_loop.run_until_complete(r.list_templates())
    # The retrieval seed is present because we preserve migration rows;
    # test-authored archived tool t1 should not appear; t2 should.
    names = {x.name for x in listed}
    assert "beta-tool" in names
    assert "alpha-tool" not in names


def test_verify_chain_integrity_passes_for_honest_chain(event_loop, repo) -> None:
    r, _ = repo
    t = _make_template()
    rev1 = _make_revision(template=t, version=1, previous_hash=GENESIS_REVISION_HASH)
    event_loop.run_until_complete(r.create_template(t, rev1))

    rev2 = _make_revision(
        template=t,
        version=2,
        previous_hash=rev1.this_revision_hash,
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer"},
            },
            "required": ["query"],
        },
    )
    event_loop.run_until_complete(r.add_revision(t.id, rev2))

    event_loop.run_until_complete(r.verify_chain_integrity(t.id))


def test_verify_chain_integrity_raises_on_template_field_tamper(
    event_loop, repo,
) -> None:
    """Tampering with ``description`` on the template row breaks the
    revision hash because D74's chain-self-containment denormalises
    description into the revision payload. The chain check surfaces
    the divergence — the D26 tamper-evidence property."""
    r, _ = repo
    t = _make_template()
    rev1 = _make_revision(template=t, version=1, previous_hash=GENESIS_REVISION_HASH)
    event_loop.run_until_complete(r.create_template(t, rev1))

    async def mutate() -> None:
        async with r._sessionmaker() as session:
            await session.execute(
                sa.update(tools)
                .where(tools.c.id == str(t.id))
                .values(description="tampered description text")
            )
            await session.commit()

    event_loop.run_until_complete(mutate())

    with pytest.raises(ValueError, match="tamper-evidence"):
        event_loop.run_until_complete(r.verify_chain_integrity(t.id))


def test_verify_chain_integrity_raises_on_unknown_tool(event_loop, repo) -> None:
    r, _ = repo
    with pytest.raises(ToolNotFoundError):
        event_loop.run_until_complete(
            r.verify_chain_integrity(uuid4())
        )


def test_retrieval_seed_chain_integrity(event_loop, repo) -> None:
    """The migration's retrieval seed must verify cleanly so the
    runtime tool surface inherits an honest chain — the load-bearing
    property the platform-managed-seed-with-fixed-UUID architecture
    rests on."""
    r, _ = repo
    retrieval_id = UUID("00000000-0000-0000-0000-000000000001")
    event_loop.run_until_complete(r.verify_chain_integrity(retrieval_id))


def test_list_roles_using_tool_returns_empty_pre_commit_4(
    event_loop, repo,
) -> None:
    """At commit 2 / 3, role.tool_allowlist is still a string array
    (names like "retrieval"); the JSONB tuple-shape pinning migration
    lands at commit 4. Before that migration, list_roles_using_tool
    finds no UUID matches and returns []."""
    r, _ = repo
    retrieval_id = UUID("00000000-0000-0000-0000-000000000001")
    bindings = event_loop.run_until_complete(
        r.list_roles_using_tool(retrieval_id)
    )
    assert bindings == []
