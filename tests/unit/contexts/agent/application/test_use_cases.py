"""Unit tests for agent use cases (D75).

Uses an in-memory fake repository to exercise the use case layer's
policy boundary, hash chain wiring, lineage-field NULL invariant on
blank-created agents, and revision-creation invariants without
touching Postgres. The integration tests at
``tests/integration/contexts/agent/adapters/outbound/postgres/``
verify the adapter against the live data plane.

Async runner pattern follows the methodology use case test file:
module-scoped event_loop fixture plus ``loop.run_until_complete``
on each coroutine call.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from contexts.agent.application import (
    archive_agent,
    create_blank_agent,
    get_agent,
    list_agents,
    update_agent,
)
from contexts.agent.domain.agent import AgentRevision, AgentTemplate
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
from shared_kernel import TenantContext, TenantId


_TENANT_A_UUID = "00000000-0000-4000-8000-00000000a001"


def _operator_principal() -> Principal:
    return Principal(
        subject="cli-operator",
        tenant_id=TenantId("operator"),
        roles=frozenset({OPERATOR_ROLE}),
        credential_ref="dev-token-op",
    )


def _tenant_principal() -> Principal:
    return Principal(
        subject="alice",
        tenant_id=TenantId(_TENANT_A_UUID),
        roles=frozenset({"agent.write"}),
        credential_ref="dev-token-a",
    )


def _unauth_principal() -> Principal:
    return Principal(
        subject="ghost",
        tenant_id=TenantId(_TENANT_A_UUID),
        roles=frozenset(),
        credential_ref="dev-token-ghost",
    )


def _tenant_context() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_A_UUID,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_A_UUID,
    )


class _FakeAgentRepository:
    def __init__(self) -> None:
        self.templates: dict[UUID, AgentTemplate] = {}
        self.revisions: dict[UUID, list[AgentRevision]] = {}
        self.calls: list[tuple[str, str]] = []

    async def create_template(
        self,
        template: AgentTemplate,
        initial_revision: AgentRevision,
        tenant_context: TenantContext,
    ) -> AgentTemplate:
        self.calls.append(("create_template", str(tenant_context.tenant_id)))
        self.templates[template.id] = template
        self.revisions[template.id] = [initial_revision]
        return template

    async def get_template(
        self,
        template_id: UUID,
        tenant_context: TenantContext,
        version: int | None = None,
    ) -> tuple[AgentTemplate, AgentRevision]:
        self.calls.append(("get_template", str(tenant_context.tenant_id)))
        if template_id not in self.templates:
            raise LookupError(f"agent template {template_id} not found")
        revs = self.revisions[template_id]
        if version is None:
            return self.templates[template_id], revs[-1]
        for r in revs:
            if r.version == version:
                return self.templates[template_id], r
        raise LookupError(
            f"agent revision for template {template_id} version {version} not found"
        )

    async def list_templates(
        self,
        tenant_context: TenantContext,
        include_archived: bool = False,
    ) -> list[AgentTemplate]:
        self.calls.append(("list_templates", str(tenant_context.tenant_id)))
        if include_archived:
            return list(self.templates.values())
        return [t for t in self.templates.values() if t.archived_at is None]

    async def add_revision(
        self,
        template_id: UUID,
        revision: AgentRevision,
        tenant_context: TenantContext,
    ) -> AgentRevision:
        self.calls.append(("add_revision", str(tenant_context.tenant_id)))
        self.revisions[template_id].append(revision)
        return revision

    async def archive_template(
        self,
        template_id: UUID,
        tenant_context: TenantContext,
    ) -> AgentTemplate:
        self.calls.append(("archive_template", str(tenant_context.tenant_id)))
        existing = self.templates[template_id]
        archived = AgentTemplate(
            id=existing.id,
            name=existing.name,
            description=existing.description,
            source_methodology_template_id=existing.source_methodology_template_id,
            source_methodology_template_version=existing.source_methodology_template_version,
            created_by_user_id=existing.created_by_user_id,
            created_at=existing.created_at,
            archived_at=datetime.now(timezone.utc),
        )
        self.templates[template_id] = archived
        return archived


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


def _create_blank(loop, repo, sec, principal=None) -> tuple[AgentTemplate, AgentRevision]:
    p = principal if principal is not None else _operator_principal()
    return loop.run_until_complete(
        create_blank_agent(
            principal=p,
            repository=repo,
            security_events=sec,
            tenant_context=_tenant_context(),
            name=f"agent-{uuid4().hex[:8]}",
            description="LVT-derived PM",
            system_prompt="You are a careful PM.",
            source_ids=(),
            tool_allowlist=(),
            retrieval_strategy={"strategy": "vector_only", "params": {}},
            filter_tree={"node": {}},
            top_k=5,
            min_score=Decimal("0.7"),
            model_selection="qwen2.5:7b",
            actor_user_id="cli-operator",
        )
    )


def test_create_blank_agent_succeeds_with_operator_context(event_loop) -> None:
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()
    template, revision = event_loop.run_until_complete(
        create_blank_agent(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            tenant_context=_tenant_context(),
            name="lvt-pm-agent",
            description="LVT-derived PM",
            system_prompt="prompt",
            source_ids=(),
            tool_allowlist=(),
            retrieval_strategy={"strategy": "vector_only", "params": {}},
            filter_tree={"node": {}},
            top_k=5,
            min_score=Decimal("0.7"),
            model_selection="qwen2.5:7b",
            actor_user_id="cli-operator",
        )
    )
    assert template.source_methodology_template_id is None
    assert template.source_methodology_template_version is None
    assert revision.version == 1
    assert revision.previous_revision_hash == GENESIS_REVISION_HASH
    assert len(revision.this_revision_hash) == 64


def test_create_blank_agent_succeeds_with_tenant_context(event_loop) -> None:
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()
    template, _ = event_loop.run_until_complete(
        create_blank_agent(
            principal=_tenant_principal(),
            repository=repo,
            security_events=sec,
            tenant_context=_tenant_context(),
            name="tenant-agent",
            description=None,
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
    assert template.id in repo.templates


def test_create_blank_agent_rejects_unauthenticated_principal(event_loop) -> None:
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()
    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            create_blank_agent(
                principal=_unauth_principal(),
                repository=repo,
                security_events=sec,
                tenant_context=_tenant_context(),
                name="ghost-agent",
                description=None,
                system_prompt="prompt",
                source_ids=(),
                tool_allowlist=(),
                retrieval_strategy={},
                filter_tree={},
                top_k=5,
                min_score=Decimal("0.7"),
                model_selection="qwen2.5:7b",
                actor_user_id="ghost",
            )
        )
    assert any(
        e.category is SecurityEventCategory.AUTHZ_DENIAL for e in sec.events
    )


def test_update_agent_chains_hash_to_predecessor(event_loop) -> None:
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()
    template, rev1 = event_loop.run_until_complete(
        create_blank_agent(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            tenant_context=_tenant_context(),
            name="ChainTest",
            description="x",
            system_prompt="v1",
            source_ids=(),
            tool_allowlist=(),
            retrieval_strategy={},
            filter_tree={},
            top_k=5,
            min_score=Decimal("0.7"),
            model_selection="qwen2.5:7b",
            actor_user_id="op",
        )
    )

    rev2 = event_loop.run_until_complete(
        update_agent(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            tenant_context=_tenant_context(),
            template_id=template.id,
            system_prompt="v2",
            source_ids=(),
            tool_allowlist=(),
            retrieval_strategy={},
            filter_tree={},
            top_k=5,
            min_score=Decimal("0.85"),
            model_selection="qwen2.5:7b",
            actor_user_id="op",
        )
    )
    assert rev2.version == 2
    assert rev2.previous_revision_hash == rev1.this_revision_hash
    assert rev2.this_revision_hash != rev1.this_revision_hash


def test_update_agent_rejects_unauthenticated_principal(event_loop) -> None:
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()
    template, _ = _create_blank(event_loop, repo, sec)

    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            update_agent(
                principal=_unauth_principal(),
                repository=repo,
                security_events=sec,
                tenant_context=_tenant_context(),
                template_id=template.id,
                system_prompt="v2",
                source_ids=(),
                tool_allowlist=(),
                retrieval_strategy={},
                filter_tree={},
                top_k=5,
                min_score=Decimal("0.85"),
                model_selection="qwen2.5:7b",
                actor_user_id="ghost",
            )
        )


def test_get_agent_returns_template_and_revision(event_loop) -> None:
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()
    template, rev1 = _create_blank(event_loop, repo, sec)

    fetched_template, fetched_rev = event_loop.run_until_complete(
        get_agent(
            principal=_tenant_principal(),
            repository=repo,
            security_events=sec,
            tenant_context=_tenant_context(),
            template_id=template.id,
        )
    )
    assert fetched_template.id == template.id
    assert fetched_rev.this_revision_hash == rev1.this_revision_hash


def test_get_agent_rejects_unauthenticated_principal(event_loop) -> None:
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()
    template, _ = _create_blank(event_loop, repo, sec)

    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            get_agent(
                principal=_unauth_principal(),
                repository=repo,
                security_events=sec,
                tenant_context=_tenant_context(),
                template_id=template.id,
            )
        )


def test_list_agents_excludes_archived_by_default(event_loop) -> None:
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()
    active, _ = _create_blank(event_loop, repo, sec)
    archived_template, _ = _create_blank(event_loop, repo, sec)
    event_loop.run_until_complete(
        archive_agent(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            tenant_context=_tenant_context(),
            template_id=archived_template.id,
        )
    )

    listed = event_loop.run_until_complete(
        list_agents(
            principal=_tenant_principal(),
            repository=repo,
            security_events=sec,
            tenant_context=_tenant_context(),
        )
    )
    listed_ids = {t.id for t in listed}
    assert active.id in listed_ids
    assert archived_template.id not in listed_ids


def test_list_agents_include_archived_returns_all(event_loop) -> None:
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()
    active, _ = _create_blank(event_loop, repo, sec)
    archived_template, _ = _create_blank(event_loop, repo, sec)
    event_loop.run_until_complete(
        archive_agent(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            tenant_context=_tenant_context(),
            template_id=archived_template.id,
        )
    )

    listed = event_loop.run_until_complete(
        list_agents(
            principal=_tenant_principal(),
            repository=repo,
            security_events=sec,
            tenant_context=_tenant_context(),
            include_archived=True,
        )
    )
    listed_ids = {t.id for t in listed}
    assert active.id in listed_ids
    assert archived_template.id in listed_ids


def test_archive_agent_marks_archived_at(event_loop) -> None:
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()
    template, _ = _create_blank(event_loop, repo, sec)

    archived = event_loop.run_until_complete(
        archive_agent(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            tenant_context=_tenant_context(),
            template_id=template.id,
        )
    )
    assert archived.archived_at is not None


def test_archive_agent_rejects_unauthenticated_principal(event_loop) -> None:
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()
    template, _ = _create_blank(event_loop, repo, sec)

    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            archive_agent(
                principal=_unauth_principal(),
                repository=repo,
                security_events=sec,
                tenant_context=_tenant_context(),
                template_id=template.id,
            )
        )


def test_use_cases_pass_tenant_context_to_repository(event_loop) -> None:
    """D75 contract: every use case threads the TenantContext through to the repo."""
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()
    template, _ = _create_blank(event_loop, repo, sec)

    event_loop.run_until_complete(
        get_agent(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            tenant_context=_tenant_context(),
            template_id=template.id,
        )
    )
    event_loop.run_until_complete(
        list_agents(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            tenant_context=_tenant_context(),
        )
    )

    # Every recorded call carries the tenant_id from the TenantContext.
    for _action, recorded_tenant_id in repo.calls:
        assert recorded_tenant_id == _TENANT_A_UUID
