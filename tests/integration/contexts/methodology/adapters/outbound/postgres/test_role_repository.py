"""Integration tests for RolePostgresRepository against the live control-plane DB (D86).

Mirrors the methodology repository integration tests shape-for-shape.
Skip gracefully when control-plane Postgres is unreachable; clean
table state at test entry and exit.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa

from contexts.methodology.adapters.outbound.postgres import (
    RolePostgresRepository,
    role_revisions,
    role_templates,
)
from contexts.methodology.domain.role import RoleRevision, RoleTemplate
from padhanam.config import ControlPlaneSettings
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
)
from padhanam.security.hash_chain import (
    GENESIS_REVISION_HASH,
    compute_revision_hash,
)


def _content_payload(
    min_score: Decimal = Decimal("0.7"),
    system_prompt: str = "v1 prompt",
    name: str = "TestRole",
) -> dict:
    return {
        "name": name,
        "description": "Integration test role fixture",
        "system_prompt": system_prompt,
        "source_ids": [],
        "tool_allowlist": [],
        "retrieval_strategy": {"strategy": "vector_only", "params": {}},
        "filter_tree": {"node": {}},
        "top_k": 5,
        "min_score": min_score,
        "model_selection": "qwen2.5:7b",
    }


def _make_template(name: str = "TestRole") -> RoleTemplate:
    return RoleTemplate(
        id=uuid4(),
        name=name,
        description="Integration test role fixture",
        created_by_user_id="alice",
        created_at=datetime.now(timezone.utc),
    )


def _make_revision(
    *,
    template_id: UUID,
    version: int,
    previous_hash: str,
    min_score: Decimal = Decimal("0.7"),
    system_prompt: str = "v1 prompt",
    name: str = "TestRole",
) -> RoleRevision:
    payload = _content_payload(min_score=min_score, system_prompt=system_prompt, name=name)
    this_hash = compute_revision_hash(content_payload=payload, previous_hash=previous_hash)
    return RoleRevision(
        id=uuid4(),
        role_template_id=template_id,
        version=version,
        system_prompt=payload["system_prompt"],
        source_ids=(),
        tool_allowlist=(),
        retrieval_strategy=payload["retrieval_strategy"],
        filter_tree=payload["filter_tree"],
        top_k=payload["top_k"],
        min_score=payload["min_score"],
        model_selection=payload["model_selection"],
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
) -> Iterator[tuple[RolePostgresRepository, _CollectingSecurityEvents]]:
    base = ControlPlaneSettings()
    settings = ControlPlaneSettings(
        user=base.user,
        password=base.password,
        db=base.db,
        host=os.environ.get("CONTROL_PLANE_HOST_OVERRIDE", "127.0.0.1"),
        port=int(os.environ.get("CONTROL_PLANE_PORT_OVERRIDE", "5433")),
    )
    sec = _CollectingSecurityEvents()
    repo = RolePostgresRepository.from_settings(
        settings=settings, security_events=sec
    )

    # Preserve migration-owned rows (e.g. 0008_create_mckinsey_7_step's
    # seven McKinsey roles); test-authored rows use distinct
    # created_by_user_id values.
    async def setup() -> None:
        async with repo._sessionmaker() as session:
            await session.execute(
                sa.delete(role_revisions).where(
                    role_revisions.c.created_by_user_id.notlike("migration:%")
                )
            )
            await session.execute(
                sa.delete(role_templates).where(
                    role_templates.c.created_by_user_id.notlike("migration:%")
                )
            )
            await session.commit()

    try:
        event_loop.run_until_complete(setup())
    except Exception as e:
        event_loop.run_until_complete(repo.dispose())
        pytest.skip(f"control-plane Postgres unreachable: {e}")
    try:
        yield repo, sec
    finally:
        async def teardown() -> None:
            async with repo._sessionmaker() as session:
                await session.execute(
                    sa.delete(role_revisions).where(
                        role_revisions.c.created_by_user_id.notlike(
                            "migration:%"
                        )
                    )
                )
                await session.execute(
                    sa.delete(role_templates).where(
                        role_templates.c.created_by_user_id.notlike(
                            "migration:%"
                        )
                    )
                )
                await session.commit()
            await repo.dispose()
        event_loop.run_until_complete(teardown())


def test_create_template_persists_template_and_initial_revision_atomically(
    event_loop, repo,
) -> None:
    r, sec = repo
    template = _make_template()
    revision = _make_revision(
        template_id=template.id, version=1, previous_hash=GENESIS_REVISION_HASH
    )
    event_loop.run_until_complete(r.create_template(template, revision))

    fetched_template, fetched_revision = event_loop.run_until_complete(
        r.get_template(template.id)
    )
    assert fetched_template.id == template.id
    assert fetched_template.name == template.name
    assert fetched_revision.version == 1
    assert fetched_revision.previous_revision_hash == GENESIS_REVISION_HASH
    assert fetched_revision.this_revision_hash == revision.this_revision_hash

    assert any(
        e.category is SecurityEventCategory.PRIVILEGED_ACTION
        and e.action == "role.create_template"
        for e in sec.events
    )


def test_add_revision_increments_version_and_chains_hash(event_loop, repo) -> None:
    r, sec = repo
    template = _make_template(name="RoleChainTest")
    revision1 = _make_revision(
        template_id=template.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="RoleChainTest",
    )
    event_loop.run_until_complete(r.create_template(template, revision1))

    revision2 = _make_revision(
        template_id=template.id, version=2,
        previous_hash=revision1.this_revision_hash,
        min_score=Decimal("0.85"), system_prompt="v2 prompt", name="RoleChainTest",
    )
    event_loop.run_until_complete(r.add_revision(template.id, revision2))

    _, fetched_v2 = event_loop.run_until_complete(
        r.get_template(template.id, version=2)
    )
    assert fetched_v2.previous_revision_hash == revision1.this_revision_hash
    assert fetched_v2.this_revision_hash == revision2.this_revision_hash
    assert fetched_v2.version == 2

    assert any(e.action == "role.add_revision" for e in sec.events)


def test_get_template_returns_latest_revision_when_version_omitted(event_loop, repo) -> None:
    r, _ = repo
    template = _make_template(name="RoleLatestTest")
    revision1 = _make_revision(
        template_id=template.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="RoleLatestTest",
    )
    event_loop.run_until_complete(r.create_template(template, revision1))

    revision2 = _make_revision(
        template_id=template.id, version=2,
        previous_hash=revision1.this_revision_hash,
        min_score=Decimal("0.9"), name="RoleLatestTest",
    )
    event_loop.run_until_complete(r.add_revision(template.id, revision2))

    _, latest = event_loop.run_until_complete(r.get_template(template.id))
    assert latest.version == 2


def test_archive_template_marks_archived_at_and_leaves_revisions_intact(event_loop, repo) -> None:
    r, sec = repo
    template = _make_template(name="RoleArchiveTest")
    revision = _make_revision(
        template_id=template.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="RoleArchiveTest",
    )
    event_loop.run_until_complete(r.create_template(template, revision))

    archived = event_loop.run_until_complete(r.archive_template(template.id))
    assert archived.archived_at is not None

    _, rev = event_loop.run_until_complete(
        r.get_template(template.id, version=1)
    )
    assert rev.version == 1
    assert rev.this_revision_hash == revision.this_revision_hash

    assert any(e.action == "role.archive_template" for e in sec.events)


def test_list_templates_excludes_archived(event_loop, repo) -> None:
    r, _ = repo
    active = _make_template(name="ActiveRole")
    active_rev = _make_revision(
        template_id=active.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="ActiveRole",
    )
    event_loop.run_until_complete(r.create_template(active, active_rev))

    archived = _make_template(name="ArchivedRole")
    archived_rev = _make_revision(
        template_id=archived.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="ArchivedRole",
    )
    event_loop.run_until_complete(r.create_template(archived, archived_rev))
    event_loop.run_until_complete(r.archive_template(archived.id))

    listed = event_loop.run_until_complete(r.list_templates())
    listed_ids = {t.id for t in listed}
    assert active.id in listed_ids
    assert archived.id not in listed_ids


def test_partial_unique_index_blocks_active_name_collision(event_loop, repo) -> None:
    r, _ = repo
    t1 = _make_template(name="RoleCollision")
    rev1 = _make_revision(
        template_id=t1.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="RoleCollision",
    )
    event_loop.run_until_complete(r.create_template(t1, rev1))

    t2 = _make_template(name="RoleCollision")
    rev2 = _make_revision(
        template_id=t2.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="RoleCollision",
    )
    with pytest.raises(Exception):
        event_loop.run_until_complete(r.create_template(t2, rev2))


def test_unique_template_version_constraint_blocks_duplicate_version(event_loop, repo) -> None:
    r, _ = repo
    template = _make_template(name="RoleDupVersion")
    revision1 = _make_revision(
        template_id=template.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="RoleDupVersion",
    )
    event_loop.run_until_complete(r.create_template(template, revision1))

    revision1_dup = _make_revision(
        template_id=template.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="RoleDupVersion",
    )
    with pytest.raises(Exception):
        event_loop.run_until_complete(r.add_revision(template.id, revision1_dup))


def test_get_template_raises_for_unknown_id(event_loop, repo) -> None:
    r, _ = repo
    with pytest.raises(LookupError):
        event_loop.run_until_complete(r.get_template(uuid4()))


def test_get_template_raises_for_unknown_version(event_loop, repo) -> None:
    r, _ = repo
    template = _make_template(name="RoleUnknownVersion")
    revision = _make_revision(
        template_id=template.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="RoleUnknownVersion",
    )
    event_loop.run_until_complete(r.create_template(template, revision))

    with pytest.raises(LookupError):
        event_loop.run_until_complete(r.get_template(template.id, version=99))
