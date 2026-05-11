"""Unit tests for create_agent_from_methodology use case (S25 / D79).

Exercises the cross-context clone flow against in-memory fakes for
MethodologyLookup, SourceLookup, and AgentRepositoryPort so the
test stays in the use case layer. Integration of the apps/cli
adapters against the live producer contexts is tested at commit 7
under tests/integration/apps/cli/; the live-stack end-to-end is
tested at commit 10 under tests/e2e/agent/.

Each test exercises one named behaviour from D79's commitments;
together the eleven tests cover the acceptance criterion that the
use case has 10+ unit tests across happy path, auth, missing-
methodology, missing-source, lineage population, content cloning,
hash-chain genesis-binding, byte-equivalence with blank-create, and
list-sort discipline on the hash payload.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from contexts.agent.application import (
    create_agent_from_methodology,
    create_blank_agent,
)
from contexts.agent.application.ports import (
    MethodologyView,
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
        raise AssertionError("create-from-methodology should not read")

    async def list_templates(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("create-from-methodology should not list")

    async def add_revision(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("create-from-methodology never adds revisions")

    async def archive_template(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("create-from-methodology never archives")


class _CollectingSecurityEvents:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def emit(self, event: SecurityEvent) -> None:
        self.events.append(event)


class _FakeMethodologyLookup:
    """Fake MethodologyLookup adapter for in-memory tests.

    Constructed with a fixed MethodologyView; the use case's request
    is captured on the instance so tests can assert the use case
    threaded the right arguments through.
    """

    def __init__(
        self,
        *,
        view: MethodologyView | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._view = view
        self._raises = raises
        self.calls: list[dict] = []

    async def __call__(
        self,
        *,
        template_id: UUID,
        version: int | None,
        principal: Principal,
    ) -> MethodologyView:
        self.calls.append(
            {"template_id": template_id, "version": version, "principal": principal}
        )
        if self._raises is not None:
            raise self._raises
        assert self._view is not None
        return self._view


class _FakeSourceLookup:
    """Fake SourceLookup adapter; either accepts all calls or raises
    SourceNotFoundError with named missing ids."""

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


def _lvt_view(
    *,
    version: int = 1,
    role_id: UUID | None = None,
    role_version: int = 1,
) -> MethodologyView:
    return MethodologyView(
        methodology_template_id=uuid4(),
        methodology_version=version,
        role_id=role_id if role_id is not None else uuid4(),
        role_version=role_version,
        description="LVT methodology assistant",
        system_prompt="You are an LVT assistant.",
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


def test_happy_path_clones_revision_1_with_paired_lineage(event_loop) -> None:
    """Top-level acceptance: cloned agent has lineage populated, revision
    1 content matches the view, repo got the create_template call."""
    view = _lvt_view(version=3)
    methodology_lookup = _FakeMethodologyLookup(view=view)
    source_lookup = _FakeSourceLookup()
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()
    src_id_1 = uuid4()
    src_id_2 = uuid4()

    template, revision = event_loop.run_until_complete(
        create_agent_from_methodology(
            principal=_operator_principal(),
            repository=repo,
            methodology_lookup=methodology_lookup,
            source_lookup=source_lookup,
            security_events=sec,
            tenant_context=_tenant_context(),
            methodology_template_id=view.methodology_template_id,
            methodology_version=None,
            name="LVT PM Agent",
            source_ids=(src_id_1, src_id_2),
            actor_user_id="cli-operator",
        )
    )

    assert template.name == "LVT PM Agent"
    assert template.description == view.description
    assert template.source_methodology_template_id == view.methodology_template_id
    assert template.source_methodology_template_version == view.methodology_version == 3
    # D86: methodology-based clone records role lineage from the
    # methodology's resolved role_refs[0] alongside methodology lineage.
    assert template.source_role_id == view.role_id
    assert template.source_role_version == view.role_version
    assert template.archived_at is None

    assert revision.version == 1
    assert revision.agent_template_id == template.id
    assert revision.system_prompt == view.system_prompt
    assert revision.tool_allowlist == view.tool_allowlist
    assert revision.retrieval_strategy == view.retrieval_strategy
    assert revision.filter_tree == view.filter_tree
    assert revision.top_k == view.top_k
    assert revision.min_score == view.min_score
    assert revision.model_selection == view.model_selection
    assert revision.source_ids == (src_id_1, src_id_2)
    assert revision.previous_revision_hash == GENESIS_REVISION_HASH
    assert revision.this_revision_hash != GENESIS_REVISION_HASH

    # Repository got exactly one create_template call.
    assert repo.calls == [("create_template", _TENANT_A_UUID)]


def test_version_none_resolves_via_methodology_lookup(event_loop) -> None:
    """The use case passes version=None through to the lookup; the
    lookup is responsible for resolving to the latest revision."""
    view = _lvt_view(version=7)
    methodology_lookup = _FakeMethodologyLookup(view=view)
    source_lookup = _FakeSourceLookup()
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()

    template, _ = event_loop.run_until_complete(
        create_agent_from_methodology(
            principal=_operator_principal(),
            repository=repo,
            methodology_lookup=methodology_lookup,
            source_lookup=source_lookup,
            security_events=sec,
            tenant_context=_tenant_context(),
            methodology_template_id=view.methodology_template_id,
            methodology_version=None,
            name="agent-none-resolved",
            source_ids=(),
            actor_user_id="cli-operator",
        )
    )

    # Lookup received version=None as requested.
    assert methodology_lookup.calls[0]["version"] is None
    # Lineage records the integer the lookup returned, not None.
    assert template.source_methodology_template_version == 7


def test_specific_version_passes_through_to_lookup(event_loop) -> None:
    """When the caller specifies a concrete version, it threads to
    the lookup unchanged and the resolved view's version is what
    gets recorded in lineage."""
    view = _lvt_view(version=2)
    methodology_lookup = _FakeMethodologyLookup(view=view)
    source_lookup = _FakeSourceLookup()
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()

    template, _ = event_loop.run_until_complete(
        create_agent_from_methodology(
            principal=_operator_principal(),
            repository=repo,
            methodology_lookup=methodology_lookup,
            source_lookup=source_lookup,
            security_events=sec,
            tenant_context=_tenant_context(),
            methodology_template_id=view.methodology_template_id,
            methodology_version=2,
            name="agent-pinned-version",
            source_ids=(),
            actor_user_id="cli-operator",
        )
    )

    assert methodology_lookup.calls[0]["version"] == 2
    assert template.source_methodology_template_version == 2


# ---------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------


def test_methodology_not_found_propagates(event_loop) -> None:
    """LookupError from the methodology adapter propagates without
    re-wrapping; the use case never reaches source validation or
    persistence."""
    methodology_lookup = _FakeMethodologyLookup(
        raises=LookupError("methodology not found")
    )
    source_lookup = _FakeSourceLookup()
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()

    with pytest.raises(LookupError):
        event_loop.run_until_complete(
            create_agent_from_methodology(
                principal=_operator_principal(),
                repository=repo,
                methodology_lookup=methodology_lookup,
                source_lookup=source_lookup,
                security_events=sec,
                tenant_context=_tenant_context(),
                methodology_template_id=uuid4(),
                methodology_version=None,
                name="agent-x",
                source_ids=(),
                actor_user_id="cli-operator",
            )
        )

    assert source_lookup.calls == []
    assert repo.calls == []


def test_source_not_found_propagates_before_persistence(event_loop) -> None:
    """SourceNotFoundError surfaces before AgentTemplate construction
    so no orphan-reference revision lands."""
    view = _lvt_view()
    missing = (uuid4(),)
    methodology_lookup = _FakeMethodologyLookup(view=view)
    source_lookup = _FakeSourceLookup(missing_ids=missing)
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()

    with pytest.raises(SourceNotFoundError) as exc_info:
        event_loop.run_until_complete(
            create_agent_from_methodology(
                principal=_operator_principal(),
                repository=repo,
                methodology_lookup=methodology_lookup,
                source_lookup=source_lookup,
                security_events=sec,
                tenant_context=_tenant_context(),
                methodology_template_id=view.methodology_template_id,
                methodology_version=None,
                name="agent-y",
                source_ids=missing,
                actor_user_id="cli-operator",
            )
        )

    assert exc_info.value.missing_source_ids == missing
    assert repo.calls == []


def test_unauthenticated_principal_raises_authorization_error(event_loop) -> None:
    """Principal with empty role set is rejected before any cross-
    context call lands. Security event recorded for audit."""
    view = _lvt_view()
    methodology_lookup = _FakeMethodologyLookup(view=view)
    source_lookup = _FakeSourceLookup()
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()

    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            create_agent_from_methodology(
                principal=_unauth_principal(),
                repository=repo,
                methodology_lookup=methodology_lookup,
                source_lookup=source_lookup,
                security_events=sec,
                tenant_context=_tenant_context(),
                methodology_template_id=view.methodology_template_id,
                methodology_version=None,
                name="agent-z",
                source_ids=(),
                actor_user_id="ghost",
            )
        )

    # No cross-context calls or persistence.
    assert methodology_lookup.calls == []
    assert source_lookup.calls == []
    assert repo.calls == []
    # Security event emitted with the correct category.
    assert len(sec.events) == 1
    assert sec.events[0].category == SecurityEventCategory.AUTHZ_DENIAL


def test_tenant_principal_authorised(event_loop) -> None:
    """Tenant-context principal (non-operator role) is also valid auth
    per D75's tenant-or-operator posture inherited at D79."""
    view = _lvt_view()
    methodology_lookup = _FakeMethodologyLookup(view=view)
    source_lookup = _FakeSourceLookup()
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()

    template, _ = event_loop.run_until_complete(
        create_agent_from_methodology(
            principal=_tenant_principal(),
            repository=repo,
            methodology_lookup=methodology_lookup,
            source_lookup=source_lookup,
            security_events=sec,
            tenant_context=_tenant_context(),
            methodology_template_id=view.methodology_template_id,
            methodology_version=None,
            name="agent-tenant-clone",
            source_ids=(),
            actor_user_id="alice",
        )
    )

    assert template.name == "agent-tenant-clone"
    assert sec.events == []  # No denial.


# ---------------------------------------------------------------------
# Hash-chain genesis-binding and byte-equivalence
# ---------------------------------------------------------------------


def test_hash_chain_genesis_binds_correctly(event_loop) -> None:
    """Revision 1's previous_revision_hash is the genesis sentinel;
    this_revision_hash is non-genesis, deterministic for given
    inputs, and length-correct for SHA-256 hex."""
    view = _lvt_view()
    methodology_lookup = _FakeMethodologyLookup(view=view)
    source_lookup = _FakeSourceLookup()
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()

    _, revision = event_loop.run_until_complete(
        create_agent_from_methodology(
            principal=_operator_principal(),
            repository=repo,
            methodology_lookup=methodology_lookup,
            source_lookup=source_lookup,
            security_events=sec,
            tenant_context=_tenant_context(),
            methodology_template_id=view.methodology_template_id,
            methodology_version=None,
            name="agent-hash-test",
            source_ids=(),
            actor_user_id="cli-operator",
        )
    )

    assert revision.previous_revision_hash == GENESIS_REVISION_HASH
    assert revision.previous_revision_hash == "0" * 64
    assert len(revision.this_revision_hash) == 64
    assert all(c in "0123456789abcdef" for c in revision.this_revision_hash)
    assert revision.this_revision_hash != GENESIS_REVISION_HASH


def test_byte_equivalent_hash_versus_blank_create(event_loop) -> None:
    """A clone with content matching what blank-create receives
    produces a byte-identical hash. This is the audit invariant D79
    commits to: chain integrity verification treats clone-created and
    blank-created revisions uniformly because they share the
    _content_payload helper invocation."""
    name = "byte-equiv-agent"
    description = "shared description"
    system_prompt = "shared prompt"
    source_ids = (uuid4(), uuid4())
    tool_allowlist = ("tool-a", "tool-b")
    retrieval_strategy = {"strategy": "hybrid", "params": {}}
    filter_tree = {"node": {}}
    top_k = 8
    min_score = Decimal("0.3")
    model_selection = "qwen2.5:7b"

    # View carries the same content fields as the blank-create call.
    view = MethodologyView(
        methodology_template_id=uuid4(),
        methodology_version=1,
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

    # Clone path.
    repo_clone = _FakeAgentRepository()
    sec_clone = _CollectingSecurityEvents()
    _, clone_revision = event_loop.run_until_complete(
        create_agent_from_methodology(
            principal=_operator_principal(),
            repository=repo_clone,
            methodology_lookup=_FakeMethodologyLookup(view=view),
            source_lookup=_FakeSourceLookup(),
            security_events=sec_clone,
            tenant_context=_tenant_context(),
            methodology_template_id=view.methodology_template_id,
            methodology_version=None,
            name=name,
            source_ids=source_ids,
            actor_user_id="cli-operator",
        )
    )

    # Blank-create path with the same content.
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


def test_source_ids_sorted_in_revision_does_not_drift_hash(event_loop) -> None:
    """The _content_payload helper sorts source_ids before hashing
    (D75); two clone calls with the same set but different orderings
    produce identical hashes. Drift prevention for the chain
    integrity check."""
    view = _lvt_view()
    a = UUID("11111111-1111-4111-8111-111111111111")
    b = UUID("22222222-2222-4222-8222-222222222222")
    c = UUID("33333333-3333-4333-8333-333333333333")

    repo_1 = _FakeAgentRepository()
    repo_2 = _FakeAgentRepository()
    sec_1 = _CollectingSecurityEvents()
    sec_2 = _CollectingSecurityEvents()

    _, rev_ordered = event_loop.run_until_complete(
        create_agent_from_methodology(
            principal=_operator_principal(),
            repository=repo_1,
            methodology_lookup=_FakeMethodologyLookup(view=view),
            source_lookup=_FakeSourceLookup(),
            security_events=sec_1,
            tenant_context=_tenant_context(),
            methodology_template_id=view.methodology_template_id,
            methodology_version=None,
            name="agent-ordered",
            source_ids=(a, b, c),
            actor_user_id="cli-operator",
        )
    )

    _, rev_shuffled = event_loop.run_until_complete(
        create_agent_from_methodology(
            principal=_operator_principal(),
            repository=repo_2,
            methodology_lookup=_FakeMethodologyLookup(view=view),
            source_lookup=_FakeSourceLookup(),
            security_events=sec_2,
            tenant_context=_tenant_context(),
            methodology_template_id=view.methodology_template_id,
            methodology_version=None,
            name="agent-ordered",
            source_ids=(c, a, b),
            actor_user_id="cli-operator",
        )
    )

    assert rev_ordered.this_revision_hash == rev_shuffled.this_revision_hash


# ---------------------------------------------------------------------
# Argument-threading discipline
# ---------------------------------------------------------------------


def test_source_lookup_receives_request_source_ids_and_tenant_context(event_loop) -> None:
    """The use case threads the request's source_ids and the routed
    tenant_context through to the SourceLookup adapter unchanged.
    Boundary-case: tenant_context is not implicit; the source lookup
    is tenant-routed per D32 and D79 records this commitment."""
    view = _lvt_view()
    methodology_lookup = _FakeMethodologyLookup(view=view)
    source_lookup = _FakeSourceLookup()
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()
    sources = (uuid4(), uuid4(), uuid4())
    ctx = _tenant_context()

    event_loop.run_until_complete(
        create_agent_from_methodology(
            principal=_operator_principal(),
            repository=repo,
            methodology_lookup=methodology_lookup,
            source_lookup=source_lookup,
            security_events=sec,
            tenant_context=ctx,
            methodology_template_id=view.methodology_template_id,
            methodology_version=None,
            name="agent-thread",
            source_ids=sources,
            actor_user_id="cli-operator",
        )
    )

    assert source_lookup.calls[0]["source_ids"] == sources
    assert source_lookup.calls[0]["tenant_context"] is ctx
    assert source_lookup.calls[0]["principal"] == _operator_principal()


def test_methodology_lookup_receives_principal_and_template_id(event_loop) -> None:
    """The methodology lookup gets the same principal the use case
    received, plus the template_id from the request. The adapter
    closes over the methodology repository; the principal threads
    through for audit-trail consistency."""
    view = _lvt_view()
    template_id = view.methodology_template_id
    principal = _operator_principal()
    methodology_lookup = _FakeMethodologyLookup(view=view)
    source_lookup = _FakeSourceLookup()
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()

    event_loop.run_until_complete(
        create_agent_from_methodology(
            principal=principal,
            repository=repo,
            methodology_lookup=methodology_lookup,
            source_lookup=source_lookup,
            security_events=sec,
            tenant_context=_tenant_context(),
            methodology_template_id=template_id,
            methodology_version=None,
            name="agent-principal-thread",
            source_ids=(),
            actor_user_id="cli-operator",
        )
    )

    assert methodology_lookup.calls[0]["template_id"] == template_id
    assert methodology_lookup.calls[0]["principal"] == principal


def test_empty_source_ids_clones_without_calling_source_lookup_with_ids(event_loop) -> None:
    """Edge case: the LVT demo populates source_ids, but the use case
    must not crash when the request carries an empty tuple (some
    methodology consumers may want to attach sources later via
    update_agent). The source lookup is still invoked with the empty
    tuple so the adapter can decide whether to short-circuit; the
    consumer-side contract does not assume non-empty input."""
    view = _lvt_view()
    methodology_lookup = _FakeMethodologyLookup(view=view)
    source_lookup = _FakeSourceLookup()
    repo = _FakeAgentRepository()
    sec = _CollectingSecurityEvents()

    template, revision = event_loop.run_until_complete(
        create_agent_from_methodology(
            principal=_operator_principal(),
            repository=repo,
            methodology_lookup=methodology_lookup,
            source_lookup=source_lookup,
            security_events=sec,
            tenant_context=_tenant_context(),
            methodology_template_id=view.methodology_template_id,
            methodology_version=None,
            name="agent-empty-sources",
            source_ids=(),
            actor_user_id="cli-operator",
        )
    )

    assert revision.source_ids == ()
    assert source_lookup.calls[0]["source_ids"] == ()
    assert template.source_methodology_template_id == view.methodology_template_id
