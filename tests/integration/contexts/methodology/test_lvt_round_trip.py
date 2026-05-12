"""Round-trip integration test for LVT methodology + LVTGuide role (S26a-1 / D86).

Exercises the end-to-end flow of the methodology v3 shape:

  1. Operator creates an LVTGuide role with the constraint bundle.
  2. Operator creates an LVT methodology referencing the role via role_refs.
  3. The MethodologyLookupAdapter resolves the methodology + role into
     a MethodologyView carrying the role's content bundle.
  4. Verify the resolved view matches the role's bundle byte-for-byte
     across the content fields.
  5. Verify the methodology revision's hash chain stays anchored at
     genesis (revision 1) and that the role revision's hash chain is
     independently anchored at genesis (role revision 1).

This is the focused round-trip the brief calls out at commit 4: it
replaces the S25 e2e test which assumed the methodology aggregate
carried the bundle directly. The S26a-2 padhanam role CLI will
restore the docker-based clone-and-edit e2e on top of this same
substrate.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from decimal import Decimal
from uuid import UUID

import pytest
import sqlalchemy as sa

from apps.cli._cross_context import MethodologyLookupAdapter
from contexts.methodology.adapters.outbound.postgres import (
    MethodologyPostgresRepository,
    RolePostgresRepository,
    methodology_revisions,
    methodology_templates,
    role_revisions,
    role_templates,
)
from contexts.methodology.application import (
    RoleRef,
    create_methodology_template,
    create_role_template,
    get_methodology_template,
    get_role_template,
)
from padhanam.config import ControlPlaneSettings
from padhanam.observability.security_events import file_security_event_logger
from padhanam.security import OPERATOR_ROLE, Principal
from padhanam.security.hash_chain import GENESIS_REVISION_HASH
from shared_kernel import TenantId, ToolAllowlistEntry


_VECTOR_SEARCH = ToolAllowlistEntry(
    tool_id=__import__("uuid").UUID("00000000-0000-4000-8000-00000000eee1"),
    revision_id=__import__("uuid").UUID("00000000-0000-4000-8000-00000000eee2"),
)
_GRAPH_TRAVERSE = ToolAllowlistEntry(
    tool_id=__import__("uuid").UUID("00000000-0000-4000-8000-00000000fff1"),
    revision_id=__import__("uuid").UUID("00000000-0000-4000-8000-00000000fff2"),
)


_LVT_SYSTEM_PROMPT = (
    "You are an LVT methodology assistant. LVT structures product "
    "strategy as bet → initiative → epic → story."
)


def _operator() -> Principal:
    return Principal(
        subject="test-operator",
        tenant_id=TenantId("operator"),
        roles=frozenset({OPERATOR_ROLE}),
        credential_ref="test-token-op",
    )


@pytest.fixture(scope="module")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture
def repos(
    event_loop: asyncio.AbstractEventLoop,
) -> Iterator[tuple[MethodologyPostgresRepository, RolePostgresRepository]]:
    base = ControlPlaneSettings()
    settings = ControlPlaneSettings(
        user=base.user,
        password=base.password,
        db=base.db,
        host=os.environ.get("CONTROL_PLANE_HOST_OVERRIDE", "127.0.0.1"),
        port=int(os.environ.get("CONTROL_PLANE_PORT_OVERRIDE", "5433")),
    )
    sec = file_security_event_logger()
    methodology_repo = MethodologyPostgresRepository.from_settings(
        settings=settings, security_events=sec
    )
    role_repo = RolePostgresRepository.from_settings(
        settings=settings, security_events=sec
    )

    async def reset() -> None:
        # Preserve migration-owned rows (e.g. 0008_create_mckinsey_7_step's
        # McKinsey 7-Step methodology and its seven roles) so the McKinsey
        # integration test at test_mckinsey_resolution.py continues to find
        # them after this fixture runs. Test-authored rows use distinct
        # created_by_user_id values ("test-operator", or operator-context
        # subjects routed through use cases).
        async with methodology_repo._sessionmaker() as session:
            await session.execute(
                sa.delete(methodology_revisions).where(
                    methodology_revisions.c.created_by_user_id.notlike(
                        "migration:%"
                    )
                )
            )
            await session.execute(
                sa.delete(methodology_templates).where(
                    methodology_templates.c.created_by_user_id.notlike(
                        "migration:%"
                    )
                )
            )
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
        event_loop.run_until_complete(reset())
    except Exception as e:
        event_loop.run_until_complete(methodology_repo.dispose())
        event_loop.run_until_complete(role_repo.dispose())
        pytest.skip(f"control-plane Postgres unreachable: {e}")
    try:
        yield methodology_repo, role_repo
    finally:
        event_loop.run_until_complete(reset())
        event_loop.run_until_complete(methodology_repo.dispose())
        event_loop.run_until_complete(role_repo.dispose())


def test_lvt_round_trip_resolves_role_content_through_methodology_view(
    event_loop, repos,
) -> None:
    methodology_repo, role_repo = repos
    sec = file_security_event_logger()

    # 1. Author the LVTGuide role.
    role_template, role_revision = event_loop.run_until_complete(
        create_role_template(
            principal=_operator(),
            repository=role_repo,
            security_events=sec,
            name="LVTGuide",
            description="Lean Value Tree guide role",
            system_prompt=_LVT_SYSTEM_PROMPT,
            source_ids=(),
            tool_allowlist=(_VECTOR_SEARCH, _GRAPH_TRAVERSE),
            retrieval_strategy={"strategy": "hybrid", "params": {}},
            filter_tree={"node": {}},
            top_k=8,
            min_score=Decimal("0.3"),
            model_selection="qwen2.5:7b",
            actor_user_id="test-operator",
        )
    )
    assert role_template.name == "LVTGuide"
    assert role_revision.version == 1
    assert role_revision.previous_revision_hash == GENESIS_REVISION_HASH
    assert role_revision.this_revision_hash != GENESIS_REVISION_HASH

    # 2. Author the LVT methodology referencing the role.
    methodology_template, methodology_revision = event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator(),
            repository=methodology_repo,
            security_events=sec,
            name="LVT",
            description="Lean Value Tree methodology",
            role_refs=(
                RoleRef(role_id=role_template.id, role_version=1),
            ),
            actor_user_id="test-operator",
        )
    )
    assert methodology_template.name == "LVT"
    assert methodology_revision.version == 1
    assert methodology_revision.previous_revision_hash == GENESIS_REVISION_HASH
    assert len(methodology_revision.role_refs) == 1
    assert methodology_revision.role_refs[0].role_id == role_template.id

    # Independent chains: methodology hash != role hash (different content surfaces).
    assert methodology_revision.this_revision_hash != role_revision.this_revision_hash

    # 3. Resolve through the cross-context adapter.
    adapter = MethodologyLookupAdapter(
        methodology_repository=methodology_repo,
        role_repository=role_repo,
    )
    view = event_loop.run_until_complete(
        adapter(
            template_id=methodology_template.id,
            version=None,
            principal=_operator(),
        )
    )

    # 4. The resolved view carries the role's bundle (no per-role
    # overrides at Phase 1 so the role's content surfaces verbatim).
    assert view.methodology_template_id == methodology_template.id
    assert view.methodology_version == 1
    assert view.description == "Lean Value Tree methodology"
    assert view.system_prompt == _LVT_SYSTEM_PROMPT
    assert view.tool_allowlist == (_VECTOR_SEARCH, _GRAPH_TRAVERSE)
    assert view.retrieval_strategy == {"strategy": "hybrid", "params": {}}
    assert view.filter_tree == {"node": {}}
    assert view.top_k == 8
    assert view.min_score == Decimal("0.3")
    assert view.model_selection == "qwen2.5:7b"

    # 5. Read methodology back via the use case directly; verify the
    # role_refs persist with the correct role_id + role_version.
    fetched_template, fetched_revision = event_loop.run_until_complete(
        get_methodology_template(
            principal=_operator(),
            repository=methodology_repo,
            template_id=methodology_template.id,
        )
    )
    assert fetched_template.id == methodology_template.id
    assert fetched_revision.this_revision_hash == methodology_revision.this_revision_hash
    assert fetched_revision.role_refs[0].role_id == role_template.id
    assert fetched_revision.role_refs[0].role_version == 1

    # 6. Read role back; verify its hash chain is independent.
    _, fetched_role_rev = event_loop.run_until_complete(
        get_role_template(
            principal=_operator(),
            repository=role_repo,
            template_id=role_template.id,
            version=1,
        )
    )
    assert fetched_role_rev.this_revision_hash == role_revision.this_revision_hash
    assert fetched_role_rev.previous_revision_hash == GENESIS_REVISION_HASH


def test_role_archival_does_not_propagate_into_methodology_view_resolution(
    event_loop, repos,
) -> None:
    """D68 clone-independence shape for role refs: the methodology's
    role_refs reference role REVISIONS (immutable per D31). Archiving
    a role's parent template doesn't break the resolution because
    revisions stay queryable after archival.
    """
    from contexts.methodology.application import retire_role_template

    methodology_repo, role_repo = repos
    sec = file_security_event_logger()

    role_template, _ = event_loop.run_until_complete(
        create_role_template(
            principal=_operator(),
            repository=role_repo,
            security_events=sec,
            name="ArchivableRole",
            description="will be archived",
            system_prompt="role prompt",
            source_ids=(),
            tool_allowlist=(),
            retrieval_strategy={"strategy": "vector_only", "params": {}},
            filter_tree={"node": {}},
            top_k=5,
            min_score=Decimal("0.7"),
            model_selection="qwen2.5:7b",
            actor_user_id="test-operator",
        )
    )
    methodology_template, _ = event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator(),
            repository=methodology_repo,
            security_events=sec,
            name="ArchTestMethodology",
            description=None,
            role_refs=(
                RoleRef(role_id=role_template.id, role_version=1),
            ),
            actor_user_id="test-operator",
        )
    )

    # Archive the role template.
    event_loop.run_until_complete(
        retire_role_template(
            principal=_operator(),
            repository=role_repo,
            security_events=sec,
            template_id=role_template.id,
        )
    )

    # The adapter still resolves the methodology because the
    # archived role's revision-1 remains queryable.
    adapter = MethodologyLookupAdapter(
        methodology_repository=methodology_repo,
        role_repository=role_repo,
    )
    view = event_loop.run_until_complete(
        adapter(
            template_id=methodology_template.id,
            version=None,
            principal=_operator(),
        )
    )
    assert view.system_prompt == "role prompt"
