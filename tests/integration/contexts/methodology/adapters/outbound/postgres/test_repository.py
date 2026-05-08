"""Integration tests for MethodologyPostgresRepository against the live control-plane DB.

The four behaviour scaffolds from
``tests/unit/contexts/methodology/ports/test_methodology_repository_port_contract.py``
move from ``@pytest.mark.skip`` to live here. Plus tests for
hash-chain integrity across multiple revisions, partial-unique-index
behaviour on archived names, and FK semantics.

The fixture pattern mirrors
``tests/contract/tenant_isolation/test_registry_isolation.py``: skip
gracefully when the control-plane Postgres is unreachable; clean
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
    MethodologyPostgresRepository,
    methodology_revisions,
    methodology_templates,
)
from padhanam.security.hash_chain import (
    GENESIS_REVISION_HASH,
    compute_revision_hash,
)
from contexts.methodology.domain.methodology import (
    MethodologyRevision,
    MethodologyTemplate,
)
from padhanam.config import ControlPlaneSettings
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
)


def _content_payload(min_score: Decimal = Decimal("0.7"), system_prompt: str = "v1 prompt") -> dict:
    return {
        "name": "TestMethodology",
        "description": "Integration test fixture",
        "system_prompt": system_prompt,
        "source_ids": [],
        "tool_allowlist": [],
        "retrieval_strategy": {"strategy": "vector_only", "params": {}},
        "filter_tree": {"node": {}},
        "top_k": 5,
        "min_score": min_score,
        "model_selection": "qwen2.5:7b",
    }


def _make_template(name: str = "TestMethodology") -> MethodologyTemplate:
    return MethodologyTemplate(
        id=uuid4(),
        name=name,
        description="Integration test fixture",
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
    name: str = "TestMethodology",
) -> MethodologyRevision:
    payload = _content_payload(min_score=min_score, system_prompt=system_prompt)
    payload["name"] = name
    this_hash = compute_revision_hash(content_payload=payload, previous_hash=previous_hash)
    return MethodologyRevision(
        id=uuid4(),
        methodology_template_id=template_id,
        version=version,
        system_prompt=payload["system_prompt"],
        source_ids=tuple(UUID(s) for s in payload["source_ids"]) if payload["source_ids"] else (),
        tool_allowlist=tuple(payload["tool_allowlist"]),
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
) -> Iterator[tuple[MethodologyPostgresRepository, _CollectingSecurityEvents]]:
    base = ControlPlaneSettings()
    settings = ControlPlaneSettings(
        user=base.user,
        password=base.password,
        db=base.db,
        host=os.environ.get("CONTROL_PLANE_HOST_OVERRIDE", "127.0.0.1"),
        port=int(os.environ.get("CONTROL_PLANE_PORT_OVERRIDE", "5433")),
    )
    sec = _CollectingSecurityEvents()
    repo = MethodologyPostgresRepository.from_settings(
        settings=settings, security_events=sec
    )

    async def setup() -> None:
        async with repo._sessionmaker() as session:
            await session.execute(sa.delete(methodology_revisions))
            await session.execute(sa.delete(methodology_templates))
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
                await session.execute(sa.delete(methodology_revisions))
                await session.execute(sa.delete(methodology_templates))
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

    # Privileged-action security event emitted on create.
    assert any(
        e.category is SecurityEventCategory.PRIVILEGED_ACTION
        and e.action == "methodology.create_template"
        for e in sec.events
    )


def test_add_revision_increments_version_and_chains_hash(event_loop, repo) -> None:
    r, sec = repo
    template = _make_template(name="ChainTest")
    revision1 = _make_revision(
        template_id=template.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="ChainTest",
    )
    event_loop.run_until_complete(r.create_template(template, revision1))

    revision2 = _make_revision(
        template_id=template.id, version=2,
        previous_hash=revision1.this_revision_hash,
        min_score=Decimal("0.85"), system_prompt="v2 prompt", name="ChainTest",
    )
    event_loop.run_until_complete(r.add_revision(template.id, revision2))

    # Verify chain: revision 2's previous_hash == revision 1's this_hash
    _, fetched_v2 = event_loop.run_until_complete(
        r.get_template(template.id, version=2)
    )
    assert fetched_v2.previous_revision_hash == revision1.this_revision_hash
    assert fetched_v2.this_revision_hash == revision2.this_revision_hash
    assert fetched_v2.version == 2

    # Privileged-action emitted on add_revision.
    assert any(
        e.action == "methodology.add_revision" for e in sec.events
    )


def test_get_template_returns_latest_revision_when_version_omitted(event_loop, repo) -> None:
    r, _ = repo
    template = _make_template(name="LatestTest")
    revision1 = _make_revision(
        template_id=template.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="LatestTest",
    )
    event_loop.run_until_complete(r.create_template(template, revision1))

    revision2 = _make_revision(
        template_id=template.id, version=2,
        previous_hash=revision1.this_revision_hash,
        min_score=Decimal("0.9"), name="LatestTest",
    )
    event_loop.run_until_complete(r.add_revision(template.id, revision2))

    revision3 = _make_revision(
        template_id=template.id, version=3,
        previous_hash=revision2.this_revision_hash,
        min_score=Decimal("0.95"), name="LatestTest",
    )
    event_loop.run_until_complete(r.add_revision(template.id, revision3))

    _, latest = event_loop.run_until_complete(r.get_template(template.id))
    assert latest.version == 3


def test_archive_template_marks_archived_at_and_leaves_revisions_intact(event_loop, repo) -> None:
    r, sec = repo
    template = _make_template(name="ArchiveTest")
    revision = _make_revision(
        template_id=template.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="ArchiveTest",
    )
    event_loop.run_until_complete(r.create_template(template, revision))

    archived = event_loop.run_until_complete(r.archive_template(template.id))
    assert archived.archived_at is not None

    # Revision is still queryable after archive.
    _, rev = event_loop.run_until_complete(
        r.get_template(template.id, version=1)
    )
    assert rev.version == 1
    assert rev.this_revision_hash == revision.this_revision_hash

    # Privileged-action emitted on archive.
    assert any(
        e.action == "methodology.archive_template" for e in sec.events
    )


def test_list_templates_excludes_archived(event_loop, repo) -> None:
    r, _ = repo
    active_template = _make_template(name="ActiveTemplate")
    active_revision = _make_revision(
        template_id=active_template.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="ActiveTemplate",
    )
    event_loop.run_until_complete(r.create_template(active_template, active_revision))

    archived_template = _make_template(name="ArchivedTemplate")
    archived_revision = _make_revision(
        template_id=archived_template.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="ArchivedTemplate",
    )
    event_loop.run_until_complete(
        r.create_template(archived_template, archived_revision)
    )
    event_loop.run_until_complete(r.archive_template(archived_template.id))

    listed = event_loop.run_until_complete(r.list_templates())
    listed_ids = {t.id for t in listed}
    assert active_template.id in listed_ids
    assert archived_template.id not in listed_ids


def test_partial_unique_index_allows_archived_name_reuse(event_loop, repo) -> None:
    """Archived templates retain their name without conflict (D31)."""
    r, _ = repo
    t1 = _make_template(name="ReuseTest")
    rev1 = _make_revision(
        template_id=t1.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="ReuseTest",
    )
    event_loop.run_until_complete(r.create_template(t1, rev1))

    # Archive t1; the name is now eligible for reuse.
    event_loop.run_until_complete(r.archive_template(t1.id))

    # New template with the same name is allowed (the partial unique
    # index only enforces uniqueness on non-archived rows).
    t2 = _make_template(name="ReuseTest")
    rev2 = _make_revision(
        template_id=t2.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="ReuseTest",
    )
    event_loop.run_until_complete(r.create_template(t2, rev2))


def test_partial_unique_index_blocks_active_name_collision(event_loop, repo) -> None:
    r, _ = repo
    t1 = _make_template(name="CollisionTest")
    rev1 = _make_revision(
        template_id=t1.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="CollisionTest",
    )
    event_loop.run_until_complete(r.create_template(t1, rev1))

    t2 = _make_template(name="CollisionTest")
    rev2 = _make_revision(
        template_id=t2.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="CollisionTest",
    )
    with pytest.raises(Exception):  # IntegrityError or wrapped form
        event_loop.run_until_complete(r.create_template(t2, rev2))


def test_unique_template_version_constraint_blocks_duplicate_version(event_loop, repo) -> None:
    r, _ = repo
    template = _make_template(name="DupVersionTest")
    revision1 = _make_revision(
        template_id=template.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="DupVersionTest",
    )
    event_loop.run_until_complete(r.create_template(template, revision1))

    # Re-add a revision with version=1 — must violate the UNIQUE
    # (methodology_template_id, version) constraint.
    revision1_dup = _make_revision(
        template_id=template.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="DupVersionTest",
    )
    with pytest.raises(Exception):
        event_loop.run_until_complete(r.add_revision(template.id, revision1_dup))


def test_get_template_raises_for_unknown_id(event_loop, repo) -> None:
    r, _ = repo
    unknown_id = uuid4()
    with pytest.raises(LookupError):
        event_loop.run_until_complete(r.get_template(unknown_id))


def test_get_template_raises_for_unknown_version(event_loop, repo) -> None:
    r, _ = repo
    template = _make_template(name="UnknownVersion")
    revision = _make_revision(
        template_id=template.id, version=1,
        previous_hash=GENESIS_REVISION_HASH, name="UnknownVersion",
    )
    event_loop.run_until_complete(r.create_template(template, revision))

    with pytest.raises(LookupError):
        event_loop.run_until_complete(r.get_template(template.id, version=99))
