"""Unit tests for role use cases (D86).

Mirrors the methodology use case test pattern shape-for-shape with an
in-memory fake repository. Exercises the use case layer's policy
boundary, hash-chain wiring, and revision-creation invariants without
touching Postgres. Integration tests at
``tests/integration/contexts/methodology/adapters/outbound/postgres/test_role_repository.py``
verify the adapter against the live control-plane DB.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from contexts.methodology.application import (
    create_role_template,
    get_role_template,
    list_role_templates,
    retire_role_template,
    update_role_template,
)
from contexts.methodology.domain.role import RoleRevision, RoleTemplate
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
)
from padhanam.security import (
    OPERATOR_ROLE,
    AuthorizationError,
    Principal,
)
from padhanam.security.hash_chain import GENESIS_REVISION_HASH
from shared_kernel import TenantId


def _operator_principal() -> Principal:
    return Principal(
        subject="system:control_plane",
        tenant_id=TenantId("operator"),
        roles=frozenset({OPERATOR_ROLE}),
        credential_ref="dev-token-op",
    )


def _tenant_principal() -> Principal:
    return Principal(
        subject="alice",
        tenant_id=TenantId("00000000-0000-4000-8000-00000000a001"),
        roles=frozenset({"audit.read"}),
        credential_ref="dev-token-a",
    )


class _FakeRoleRepository:
    def __init__(self) -> None:
        self.templates: dict[UUID, RoleTemplate] = {}
        self.revisions: dict[UUID, list[RoleRevision]] = {}

    async def create_template(
        self,
        template: RoleTemplate,
        initial_revision: RoleRevision,
    ) -> RoleTemplate:
        self.templates[template.id] = template
        self.revisions[template.id] = [initial_revision]
        return template

    async def get_template(
        self,
        template_id: UUID,
        version: int | None = None,
    ) -> tuple[RoleTemplate, RoleRevision]:
        if template_id not in self.templates:
            raise LookupError(f"role template {template_id} not found")
        revs = self.revisions[template_id]
        if version is None:
            return self.templates[template_id], revs[-1]
        for rev in revs:
            if rev.version == version:
                return self.templates[template_id], rev
        raise LookupError(
            f"revision for role template {template_id} version {version} not found"
        )

    async def list_templates(self) -> list[RoleTemplate]:
        return [t for t in self.templates.values() if t.archived_at is None]

    async def add_revision(
        self,
        template_id: UUID,
        revision: RoleRevision,
    ) -> RoleRevision:
        self.revisions[template_id].append(revision)
        return revision

    async def archive_template(
        self,
        template_id: UUID,
    ) -> RoleTemplate:
        template = self.templates[template_id]
        archived = RoleTemplate(
            id=template.id,
            name=template.name,
            description=template.description,
            created_by_user_id=template.created_by_user_id,
            created_at=template.created_at,
            archived_at=datetime.now(timezone.utc),
        )
        self.templates[template_id] = archived
        return archived


class _CollectingSecurityEvents:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def emit(self, event: SecurityEvent) -> None:
        self.events.append(event)


def _create_kwargs(**overrides) -> dict:
    defaults = {
        "name": "TestRole",
        "description": "Test role fixture",
        "system_prompt": "You are a careful analyst.",
        "source_ids": (),
        "tool_allowlist": (),
        "retrieval_strategy": {"strategy": "vector_only", "params": {}},
        "filter_tree": {"node": {}},
        "top_k": 5,
        "min_score": Decimal("0.7"),
        "model_selection": "qwen2.5:7b",
        "actor_user_id": "alice",
    }
    defaults.update(overrides)
    return defaults


@pytest.fixture(scope="module")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


def test_create_role_template_operator_succeeds(event_loop) -> None:
    repo = _FakeRoleRepository()
    sec = _CollectingSecurityEvents()
    template, revision = event_loop.run_until_complete(
        create_role_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(),
        )
    )
    assert template.name == "TestRole"
    assert revision.version == 1
    assert revision.previous_revision_hash == GENESIS_REVISION_HASH
    assert len(revision.this_revision_hash) == 64


def test_create_role_template_tenant_rejected(event_loop) -> None:
    repo = _FakeRoleRepository()
    sec = _CollectingSecurityEvents()
    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            create_role_template(
                principal=_tenant_principal(),
                repository=repo,
                security_events=sec,
                **_create_kwargs(),
            )
        )
    assert repo.templates == {}
    assert any(
        e.category is SecurityEventCategory.AUTHZ_DENIAL
        and e.action == "role.create_template"
        for e in sec.events
    )


def test_update_role_template_chains_hash_to_predecessor(event_loop) -> None:
    repo = _FakeRoleRepository()
    sec = _CollectingSecurityEvents()
    template, rev1 = event_loop.run_until_complete(
        create_role_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(),
        )
    )
    rev2 = event_loop.run_until_complete(
        update_role_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            template_id=template.id,
            system_prompt="Updated role prompt",
            source_ids=(),
            tool_allowlist=(),
            retrieval_strategy={"strategy": "vector_only", "params": {}},
            filter_tree={"node": {}},
            top_k=5,
            min_score=Decimal("0.85"),
            model_selection="qwen2.5:7b",
            actor_user_id="alice",
        )
    )
    assert rev2.version == 2
    assert rev2.previous_revision_hash == rev1.this_revision_hash
    assert rev2.this_revision_hash != rev1.this_revision_hash


def test_update_role_template_tenant_rejected(event_loop) -> None:
    repo = _FakeRoleRepository()
    sec = _CollectingSecurityEvents()
    template, _ = event_loop.run_until_complete(
        create_role_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(),
        )
    )
    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            update_role_template(
                principal=_tenant_principal(),
                repository=repo,
                security_events=sec,
                template_id=template.id,
                system_prompt="Updated role prompt",
                source_ids=(),
                tool_allowlist=(),
                retrieval_strategy={"strategy": "vector_only", "params": {}},
                filter_tree={"node": {}},
                top_k=5,
                min_score=Decimal("0.85"),
                model_selection="qwen2.5:7b",
                actor_user_id="alice",
            )
        )
    assert len(repo.revisions[template.id]) == 1
    assert any(
        e.category is SecurityEventCategory.AUTHZ_DENIAL
        and e.action == "role.update_template"
        for e in sec.events
    )


def test_get_role_template_accepts_tenant_context(event_loop) -> None:
    repo = _FakeRoleRepository()
    sec = _CollectingSecurityEvents()
    template, _ = event_loop.run_until_complete(
        create_role_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(),
        )
    )
    fetched_template, fetched_rev = event_loop.run_until_complete(
        get_role_template(
            principal=_tenant_principal(),
            repository=repo,
            template_id=template.id,
        )
    )
    assert fetched_template.id == template.id
    assert fetched_rev.version == 1


def test_get_role_template_returns_named_version(event_loop) -> None:
    repo = _FakeRoleRepository()
    sec = _CollectingSecurityEvents()
    template, _ = event_loop.run_until_complete(
        create_role_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(),
        )
    )
    event_loop.run_until_complete(
        update_role_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            template_id=template.id,
            system_prompt="Updated role prompt v2",
            source_ids=(),
            tool_allowlist=(),
            retrieval_strategy={"strategy": "vector_only", "params": {}},
            filter_tree={"node": {}},
            top_k=5,
            min_score=Decimal("0.85"),
            model_selection="qwen2.5:7b",
            actor_user_id="alice",
        )
    )
    _, named = event_loop.run_until_complete(
        get_role_template(
            principal=_operator_principal(),
            repository=repo,
            template_id=template.id,
            version=1,
        )
    )
    assert named.version == 1
    assert named.system_prompt == "You are a careful analyst."


def test_list_role_templates_excludes_archived(event_loop) -> None:
    repo = _FakeRoleRepository()
    sec = _CollectingSecurityEvents()
    keep, _ = event_loop.run_until_complete(
        create_role_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(name="RoleKeep"),
        )
    )
    drop, _ = event_loop.run_until_complete(
        create_role_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(name="RoleDrop"),
        )
    )
    event_loop.run_until_complete(
        retire_role_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            template_id=drop.id,
        )
    )
    listed = event_loop.run_until_complete(
        list_role_templates(
            principal=_tenant_principal(),
            repository=repo,
        )
    )
    assert {t.id for t in listed} == {keep.id}


def test_retire_role_template_tenant_rejected(event_loop) -> None:
    repo = _FakeRoleRepository()
    sec = _CollectingSecurityEvents()
    template, _ = event_loop.run_until_complete(
        create_role_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(),
        )
    )
    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            retire_role_template(
                principal=_tenant_principal(),
                repository=repo,
                security_events=sec,
                template_id=template.id,
            )
        )
    assert repo.templates[template.id].archived_at is None
    assert any(
        e.category is SecurityEventCategory.AUTHZ_DENIAL
        and e.action == "role.retire_template"
        for e in sec.events
    )


def test_hash_chain_byte_equivalence_under_list_field_reorder(event_loop) -> None:
    """Hash determinism (D75): source_ids and tool_allowlist sorted at the use case layer."""
    src_a = uuid4()
    src_b = uuid4()
    repo1 = _FakeRoleRepository()
    repo2 = _FakeRoleRepository()
    sec = _CollectingSecurityEvents()
    _, rev1 = event_loop.run_until_complete(
        create_role_template(
            principal=_operator_principal(),
            repository=repo1,
            security_events=sec,
            **_create_kwargs(
                source_ids=(src_a, src_b),
                tool_allowlist=("tool_b", "tool_a"),
            ),
        )
    )
    _, rev2 = event_loop.run_until_complete(
        create_role_template(
            principal=_operator_principal(),
            repository=repo2,
            security_events=sec,
            **_create_kwargs(
                source_ids=(src_b, src_a),
                tool_allowlist=("tool_a", "tool_b"),
            ),
        )
    )
    assert rev1.this_revision_hash == rev2.this_revision_hash
