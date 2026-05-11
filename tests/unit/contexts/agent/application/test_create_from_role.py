"""Unit tests for create_agent_from_role use case (S26a-2 / D86).

Exercises the direct role-clone flow against in-memory fakes for
RoleLookup, SourceLookup, and AgentRepositoryPort, mirroring the
shape of test_create_from_methodology.py. The role-clone path is the
D86 first-class-role posture: agents can occupy a role directly
without a methodology playbook above them.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from contexts.agent.application import (
    create_agent_from_role,
    create_blank_agent,
)
from contexts.agent.application.ports import (
    RoleView,
    SourceNotFoundError,
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

    async def get_template(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("create-from-role should not read")

    async def list_templates(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("create-from-role should not list")

    async def add_revision(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("create-from-role never adds revisions")

    async def archive_template(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("create-from-role never archives")


class _CollectingSecurityEvents:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def emit(self, event: SecurityEvent) -> None:
        self.events.append(event)


class _FakeRoleLookup:
    def __init__(
        self,
        *,
        view: RoleView | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._view = view
        self._raises = raises
        self.calls: list[dict] = []

    async def __call__(
        self,
        *,
        role_id: UUID,
        version: int | None,
        principal: Principal,
    ) -> RoleView:
        self.calls.append(
            {"role_id": role_id, "version": version, "principal": principal}
        )
        if self._raises is not None:
            raise self._raises
        assert self._view is not None
        return self._view


class _FakeSourceLookup:
    def __init__(
        self,
        *,
        missing_ids: tuple[UUID, ...] | None = None,
    ) -> None:
        self._missing_ids = missing_ids
        self.calls: list[dict] = []

    async def assert_sources_exist(
        self,
        *,
        source_ids: tuple[UUID, ...],
        tenant_context: TenantContext,
        principal: Principal,
    ) -> None:
        self.calls.append(
            {
                "source_ids": source_ids,
                "tenant_context": tenant_context,
                "principal": principal,
            }
        )
        if self._missing_ids:
            raise SourceNotFoundError(missing_source_ids=self._missing_ids)


@pytest.fixture(scope="module")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


def _lvtguide_view(*, version: int = 1, role_id: UUID | None = None) -> RoleView:
    return RoleView(
        role_id=role_id if role_id is not None else uuid4(),
        role_version=version,
        description="LVTGuide role: places work in the LVT hierarchy",
        system_prompt="You are an LVTGuide role.",
        tool_allowlist=(),
        retrieval_strategy={"strategy": "hybrid", "params": {}},
        filter_tree={"node": {}},
        top_k=8,
        min_score=Decimal("0.3"),
        model_selection="qwen2.5:7b",
    )


# ---------------------------------------------------------------------
# Happy path and structural correctness
# ---------------------------------------------------------------------


def test_happy_path_clones_role_with_role_only_lineage(event_loop) -> None:
    """D86 third-valid-state: only the role pair is populated; the
    methodology pair stays NULL because the agent did not come
    through a methodology playbook."""
    view = _lvtguide_view(version=2)
    role_lookup = _FakeRoleLookup(view=view)
    source_lookup = _FakeSourceLookup()
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()
    src_id = uuid4()

    template, revision = event_loop.run_until_complete(
        create_agent_from_role(
            principal=_operator_principal(),
            repository=repo,
            role_lookup=role_lookup,
            source_lookup=source_lookup,
            security_events=sec,
            tenant_context=_tenant_context(),
            role_id=view.role_id,
            role_version=None,
            name="LVTGuide Direct Agent",
            source_ids=(src_id,),
            actor_user_id="cli-operator",
        )
    )

    assert template.name == "LVTGuide Direct Agent"
    assert template.description == view.description
    # Methodology lineage is NULL (third valid state).
    assert template.source_methodology_template_id is None
    assert template.source_methodology_template_version is None
    # Role lineage carries resolved (id, version).
    assert template.source_role_id == view.role_id
    assert template.source_role_version == view.role_version == 2

    assert revision.version == 1
    assert revision.agent_template_id == template.id
    assert revision.system_prompt == view.system_prompt
    assert revision.previous_revision_hash == GENESIS_REVISION_HASH
    assert revision.source_ids == (src_id,)


def test_version_none_resolves_via_role_lookup(event_loop) -> None:
    view = _lvtguide_view(version=5)
    role_lookup = _FakeRoleLookup(view=view)
    source_lookup = _FakeSourceLookup()
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()

    template, _ = event_loop.run_until_complete(
        create_agent_from_role(
            principal=_operator_principal(),
            repository=repo,
            role_lookup=role_lookup,
            source_lookup=source_lookup,
            security_events=sec,
            tenant_context=_tenant_context(),
            role_id=view.role_id,
            role_version=None,
            name="agent-none-resolved",
            source_ids=(),
            actor_user_id="cli-operator",
        )
    )

    assert role_lookup.calls[0]["version"] is None
    assert template.source_role_version == 5


def test_specific_role_version_passes_through(event_loop) -> None:
    view = _lvtguide_view(version=2)
    role_lookup = _FakeRoleLookup(view=view)
    source_lookup = _FakeSourceLookup()
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()

    template, _ = event_loop.run_until_complete(
        create_agent_from_role(
            principal=_operator_principal(),
            repository=repo,
            role_lookup=role_lookup,
            source_lookup=source_lookup,
            security_events=sec,
            tenant_context=_tenant_context(),
            role_id=view.role_id,
            role_version=2,
            name="agent-pinned-version",
            source_ids=(),
            actor_user_id="cli-operator",
        )
    )

    assert role_lookup.calls[0]["version"] == 2
    assert template.source_role_version == 2


# ---------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------


def test_role_not_found_propagates(event_loop) -> None:
    role_lookup = _FakeRoleLookup(raises=LookupError("role not found"))
    source_lookup = _FakeSourceLookup()
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()

    with pytest.raises(LookupError):
        event_loop.run_until_complete(
            create_agent_from_role(
                principal=_operator_principal(),
                repository=repo,
                role_lookup=role_lookup,
                source_lookup=source_lookup,
                security_events=sec,
                tenant_context=_tenant_context(),
                role_id=uuid4(),
                role_version=None,
                name="agent-x",
                source_ids=(),
                actor_user_id="cli-operator",
            )
        )

    assert source_lookup.calls == []
    assert repo.calls == []


def test_source_not_found_propagates_before_persistence(event_loop) -> None:
    view = _lvtguide_view()
    missing = (uuid4(),)
    role_lookup = _FakeRoleLookup(view=view)
    source_lookup = _FakeSourceLookup(missing_ids=missing)
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()

    with pytest.raises(SourceNotFoundError) as exc_info:
        event_loop.run_until_complete(
            create_agent_from_role(
                principal=_operator_principal(),
                repository=repo,
                role_lookup=role_lookup,
                source_lookup=source_lookup,
                security_events=sec,
                tenant_context=_tenant_context(),
                role_id=view.role_id,
                role_version=None,
                name="agent-y",
                source_ids=missing,
                actor_user_id="cli-operator",
            )
        )

    assert exc_info.value.missing_source_ids == missing
    assert repo.calls == []


def test_unauthenticated_principal_raises_authz(event_loop) -> None:
    view = _lvtguide_view()
    role_lookup = _FakeRoleLookup(view=view)
    source_lookup = _FakeSourceLookup()
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()

    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            create_agent_from_role(
                principal=_unauth_principal(),
                repository=repo,
                role_lookup=role_lookup,
                source_lookup=source_lookup,
                security_events=sec,
                tenant_context=_tenant_context(),
                role_id=view.role_id,
                role_version=None,
                name="agent-z",
                source_ids=(),
                actor_user_id="ghost",
            )
        )

    assert role_lookup.calls == []
    assert source_lookup.calls == []
    assert repo.calls == []
    assert len(sec.events) == 1
    assert sec.events[0].category == SecurityEventCategory.AUTHZ_DENIAL


def test_tenant_principal_authorised(event_loop) -> None:
    """Tenant-context principal (non-operator) is valid auth per
    D75's tenant-or-operator posture inherited at D86."""
    view = _lvtguide_view()
    role_lookup = _FakeRoleLookup(view=view)
    source_lookup = _FakeSourceLookup()
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()

    template, _ = event_loop.run_until_complete(
        create_agent_from_role(
            principal=_tenant_principal(),
            repository=repo,
            role_lookup=role_lookup,
            source_lookup=source_lookup,
            security_events=sec,
            tenant_context=_tenant_context(),
            role_id=view.role_id,
            role_version=None,
            name="agent-tenant-clone",
            source_ids=(),
            actor_user_id="alice",
        )
    )

    assert template.name == "agent-tenant-clone"
    assert sec.events == []


# ---------------------------------------------------------------------
# Hash chain
# ---------------------------------------------------------------------


def test_hash_chain_genesis_binds_correctly(event_loop) -> None:
    view = _lvtguide_view()
    role_lookup = _FakeRoleLookup(view=view)
    source_lookup = _FakeSourceLookup()
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()

    _, revision = event_loop.run_until_complete(
        create_agent_from_role(
            principal=_operator_principal(),
            repository=repo,
            role_lookup=role_lookup,
            source_lookup=source_lookup,
            security_events=sec,
            tenant_context=_tenant_context(),
            role_id=view.role_id,
            role_version=None,
            name="agent-hash-test",
            source_ids=(),
            actor_user_id="cli-operator",
        )
    )

    assert revision.previous_revision_hash == GENESIS_REVISION_HASH
    assert len(revision.this_revision_hash) == 64
    assert revision.this_revision_hash != GENESIS_REVISION_HASH


def test_byte_equivalent_hash_versus_blank_create(event_loop) -> None:
    """A clone-from-role with content matching blank-create produces a
    byte-identical hash. Per D75 chain-self-containment, all three
    create paths share _content_payload, so audit-time verification
    treats role-cloned and blank-created agents uniformly."""
    name = "byte-equiv-role-agent"
    description = "shared description"
    system_prompt = "shared prompt"
    source_ids = (uuid4(), uuid4())
    tool_allowlist = ("tool-a", "tool-b")
    retrieval_strategy = {"strategy": "hybrid", "params": {}}
    filter_tree = {"node": {}}
    top_k = 8
    min_score = Decimal("0.3")
    model_selection = "qwen2.5:7b"

    view = RoleView(
        role_id=uuid4(),
        role_version=1,
        description=description,
        system_prompt=system_prompt,
        tool_allowlist=tool_allowlist,
        retrieval_strategy=retrieval_strategy,
        filter_tree=filter_tree,
        top_k=top_k,
        min_score=min_score,
        model_selection=model_selection,
    )

    repo_clone = _FakeAgentRepository()
    sec_clone = _CollectingSecurityEvents()
    _, clone_revision = event_loop.run_until_complete(
        create_agent_from_role(
            principal=_operator_principal(),
            repository=repo_clone,
            role_lookup=_FakeRoleLookup(view=view),
            source_lookup=_FakeSourceLookup(),
            security_events=sec_clone,
            tenant_context=_tenant_context(),
            role_id=view.role_id,
            role_version=None,
            name=name,
            source_ids=source_ids,
            actor_user_id="cli-operator",
        )
    )

    repo_blank = _FakeAgentRepository()
    sec_blank = _CollectingSecurityEvents()
    _, blank_revision = event_loop.run_until_complete(
        create_blank_agent(
            principal=_operator_principal(),
            repository=repo_blank,
            security_events=sec_blank,
            tenant_context=_tenant_context(),
            name=name,
            description=description,
            system_prompt=system_prompt,
            source_ids=source_ids,
            tool_allowlist=tool_allowlist,
            retrieval_strategy=retrieval_strategy,
            filter_tree=filter_tree,
            top_k=top_k,
            min_score=min_score,
            model_selection=model_selection,
            actor_user_id="cli-operator",
        )
    )

    assert clone_revision.this_revision_hash == blank_revision.this_revision_hash


# ---------------------------------------------------------------------
# Argument threading
# ---------------------------------------------------------------------


def test_source_lookup_receives_request_source_ids_and_tenant_context(
    event_loop,
) -> None:
    view = _lvtguide_view()
    role_lookup = _FakeRoleLookup(view=view)
    source_lookup = _FakeSourceLookup()
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()
    sources = (uuid4(), uuid4())
    ctx = _tenant_context()

    event_loop.run_until_complete(
        create_agent_from_role(
            principal=_operator_principal(),
            repository=repo,
            role_lookup=role_lookup,
            source_lookup=source_lookup,
            security_events=sec,
            tenant_context=ctx,
            role_id=view.role_id,
            role_version=None,
            name="agent-thread",
            source_ids=sources,
            actor_user_id="cli-operator",
        )
    )

    assert source_lookup.calls[0]["source_ids"] == sources
    assert source_lookup.calls[0]["tenant_context"] is ctx


def test_role_lookup_receives_principal_and_role_id(event_loop) -> None:
    view = _lvtguide_view()
    role_id = view.role_id
    principal = _operator_principal()
    role_lookup = _FakeRoleLookup(view=view)
    source_lookup = _FakeSourceLookup()
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()

    event_loop.run_until_complete(
        create_agent_from_role(
            principal=principal,
            repository=repo,
            role_lookup=role_lookup,
            source_lookup=source_lookup,
            security_events=sec,
            tenant_context=_tenant_context(),
            role_id=role_id,
            role_version=None,
            name="agent-principal-thread",
            source_ids=(),
            actor_user_id="cli-operator",
        )
    )

    assert role_lookup.calls[0]["role_id"] == role_id
    assert role_lookup.calls[0]["principal"] == principal
