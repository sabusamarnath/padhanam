"""Unit tests for methodology use cases (D74).

Uses an in-memory fake repository to exercise the use case layer's
policy boundary, hash chain wiring, and revision-creation invariants
without touching Postgres. The integration tests at
``tests/integration/contexts/methodology/adapters/outbound/postgres/``
verify the adapter against the live control-plane DB.

Async runner pattern follows
``tests/contract/tenant_isolation/test_registry_isolation.py``:
module-scoped event_loop fixture plus ``loop.run_until_complete``
on each coroutine call. No pytest-asyncio dependency.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from contexts.methodology.application import (
    create_methodology_template,
    get_methodology_template,
    list_methodology_templates,
    retire_methodology_template,
    update_methodology_template,
)
from contexts.methodology.domain.hash_chain import GENESIS_REVISION_HASH
from contexts.methodology.domain.methodology import (
    MethodologyRevision,
    MethodologyTemplate,
)
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
)
from padhanam.security import (
    OPERATOR_ROLE,
    AuthorizationError,
    Principal,
)
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


class _FakeMethodologyRepository:
    def __init__(self) -> None:
        self.templates: dict[UUID, MethodologyTemplate] = {}
        self.revisions: dict[UUID, list[MethodologyRevision]] = {}

    async def create_template(
        self,
        template: MethodologyTemplate,
        initial_revision: MethodologyRevision,
    ) -> MethodologyTemplate:
        self.templates[template.id] = template
        self.revisions[template.id] = [initial_revision]
        return template

    async def get_template(
        self,
        template_id: UUID,
        version: int | None = None,
    ) -> tuple[MethodologyTemplate, MethodologyRevision]:
        if template_id not in self.templates:
            raise LookupError(f"methodology template {template_id} not found")
        revs = self.revisions[template_id]
        if version is None:
            return self.templates[template_id], revs[-1]
        for rev in revs:
            if rev.version == version:
                return self.templates[template_id], rev
        raise LookupError(
            f"revision for template {template_id} version {version} not found"
        )

    async def list_templates(self) -> list[MethodologyTemplate]:
        return [t for t in self.templates.values() if t.archived_at is None]

    async def add_revision(
        self,
        template_id: UUID,
        revision: MethodologyRevision,
    ) -> MethodologyRevision:
        self.revisions[template_id].append(revision)
        return revision

    async def archive_template(
        self,
        template_id: UUID,
    ) -> MethodologyTemplate:
        template = self.templates[template_id]
        archived = MethodologyTemplate(
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
        "name": "TestMethodology",
        "description": "Test fixture",
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


def test_create_methodology_template_operator_succeeds(event_loop) -> None:
    repo = _FakeMethodologyRepository()
    sec = _CollectingSecurityEvents()
    template, revision = event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(),
        )
    )
    assert template.name == "TestMethodology"
    assert revision.version == 1
    assert revision.previous_revision_hash == GENESIS_REVISION_HASH
    assert len(revision.this_revision_hash) == 64


def test_create_methodology_template_tenant_rejected(event_loop) -> None:
    repo = _FakeMethodologyRepository()
    sec = _CollectingSecurityEvents()
    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            create_methodology_template(
                principal=_tenant_principal(),
                repository=repo,
                security_events=sec,
                **_create_kwargs(),
            )
        )
    assert repo.templates == {}
    assert any(
        e.category is SecurityEventCategory.AUTHZ_DENIAL
        and e.action == "methodology.create_template"
        for e in sec.events
    )


def test_update_methodology_template_chains_hash_to_predecessor(event_loop) -> None:
    repo = _FakeMethodologyRepository()
    sec = _CollectingSecurityEvents()
    template, rev1 = event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(),
        )
    )
    rev2 = event_loop.run_until_complete(
        update_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            template_id=template.id,
            system_prompt="Updated prompt",
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


def test_update_methodology_template_tenant_rejected(event_loop) -> None:
    repo = _FakeMethodologyRepository()
    sec = _CollectingSecurityEvents()
    template, _ = event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(),
        )
    )
    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            update_methodology_template(
                principal=_tenant_principal(),
                repository=repo,
                security_events=sec,
                template_id=template.id,
                system_prompt="Updated prompt",
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
        and e.action == "methodology.update_template"
        for e in sec.events
    )


def test_get_methodology_template_accepts_tenant_context(event_loop) -> None:
    repo = _FakeMethodologyRepository()
    sec = _CollectingSecurityEvents()
    template, _ = event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(),
        )
    )
    fetched_template, fetched_rev = event_loop.run_until_complete(
        get_methodology_template(
            principal=_tenant_principal(),
            repository=repo,
            template_id=template.id,
        )
    )
    assert fetched_template.id == template.id
    assert fetched_rev.version == 1


def test_get_methodology_template_returns_named_version(event_loop) -> None:
    repo = _FakeMethodologyRepository()
    sec = _CollectingSecurityEvents()
    template, _ = event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(),
        )
    )
    event_loop.run_until_complete(
        update_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            template_id=template.id,
            system_prompt="v2",
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
    _, v1 = event_loop.run_until_complete(
        get_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            template_id=template.id,
            version=1,
        )
    )
    _, v2 = event_loop.run_until_complete(
        get_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            template_id=template.id,
            version=2,
        )
    )
    assert v1.version == 1
    assert v2.version == 2


def test_list_methodology_templates_accepts_tenant_context(event_loop) -> None:
    repo = _FakeMethodologyRepository()
    sec = _CollectingSecurityEvents()
    event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(name="A"),
        )
    )
    event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(name="B"),
        )
    )
    listed = event_loop.run_until_complete(
        list_methodology_templates(
            principal=_tenant_principal(),
            repository=repo,
        )
    )
    assert {t.name for t in listed} == {"A", "B"}


def test_retire_methodology_template_operator_succeeds(event_loop) -> None:
    repo = _FakeMethodologyRepository()
    sec = _CollectingSecurityEvents()
    template, _ = event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(),
        )
    )
    archived = event_loop.run_until_complete(
        retire_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            template_id=template.id,
        )
    )
    assert archived.archived_at is not None


def test_retire_methodology_template_tenant_rejected(event_loop) -> None:
    repo = _FakeMethodologyRepository()
    sec = _CollectingSecurityEvents()
    template, _ = event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(),
        )
    )
    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            retire_methodology_template(
                principal=_tenant_principal(),
                repository=repo,
                security_events=sec,
                template_id=template.id,
            )
        )
    assert repo.templates[template.id].archived_at is None
    assert any(
        e.action == "methodology.retire_template"
        and e.category is SecurityEventCategory.AUTHZ_DENIAL
        for e in sec.events
    )


def test_retire_methodology_template_leaves_revisions_intact(event_loop) -> None:
    """D68: existing clone references survive retirement."""
    repo = _FakeMethodologyRepository()
    sec = _CollectingSecurityEvents()
    template, original_rev = event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(),
        )
    )
    event_loop.run_until_complete(
        retire_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            template_id=template.id,
        )
    )
    _, fetched_rev = event_loop.run_until_complete(
        get_methodology_template(
            principal=_tenant_principal(),
            repository=repo,
            template_id=template.id,
            version=1,
        )
    )
    assert fetched_rev.id == original_rev.id
    assert fetched_rev.this_revision_hash == original_rev.this_revision_hash


def test_create_methodology_template_uses_genesis_for_revision_one(event_loop) -> None:
    repo = _FakeMethodologyRepository()
    sec = _CollectingSecurityEvents()
    _, rev = event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(),
        )
    )
    assert rev.previous_revision_hash == GENESIS_REVISION_HASH


def test_update_methodology_template_propagates_lookuperror_for_unknown_id(event_loop) -> None:
    repo = _FakeMethodologyRepository()
    sec = _CollectingSecurityEvents()
    unknown_id = uuid4()
    with pytest.raises(LookupError):
        event_loop.run_until_complete(
            update_methodology_template(
                principal=_operator_principal(),
                repository=repo,
                security_events=sec,
                template_id=unknown_id,
                system_prompt="prompt",
                source_ids=(),
                tool_allowlist=(),
                retrieval_strategy={"strategy": "vector_only", "params": {}},
                filter_tree={"node": {}},
                top_k=5,
                min_score=Decimal("0.7"),
                model_selection="qwen2.5:7b",
                actor_user_id="alice",
            )
        )
