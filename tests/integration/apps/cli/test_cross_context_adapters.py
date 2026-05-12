"""Integration tests for the apps/cli cross-context adapters (S25 / D79, refactored S26a-1 / D86).

Exercises MethodologyLookupAdapter and SourceLookupAdapter through
the real producer-side application use cases
(``get_methodology_template`` + ``get_role_template`` from methodology;
``get_source`` from ingestion) against in-memory fake repositories.
The integration scope here is "adapter + real producer use cases +
in-memory repo" — the database layer is tested by the methodology
and ingestion adapter integration suites; the e2e against the full
live stack lands at commit 10.

S26a-1 refactor per D86: the MethodologyLookupAdapter now resolves
``role_refs`` via the role repository at lookup time and populates the
consumer-side MethodologyView with the resolved role's content bundle.
The tests below construct both a methodology revision (carrying a
role_ref) and a role revision (carrying the bundle); the adapter
joins the two at __call__ time.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from apps.cli._cross_context import (
    AgentRetrievalClientAdapter,
    MethodologyLookupAdapter,
    MethodologyOverridesLookupAdapter,
    RoleLookupAdapter,
    SourceLookupAdapter,
)
from contexts.agent.application.ports import (
    MethodologyView,
    RoleView,
    SourceNotFoundError,
)
from contexts.ingestion.domain.source import Source
from contexts.ingestion.domain.state import SourceState
from contexts.methodology.domain.methodology import (
    MethodologyRevision,
    MethodologyTemplate,
    RoleRef,
)
from contexts.methodology.domain.role import RoleRevision, RoleTemplate
from padhanam.security import OPERATOR_ROLE, Principal
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


def _tenant_context() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_A_UUID,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_A_UUID,
    )


def _make_methodology_template(*, template_id: UUID, description: str | None) -> MethodologyTemplate:
    return MethodologyTemplate(
        id=template_id,
        name="LVT",
        description=description,
        created_by_user_id="cli-operator",
        created_at=datetime.now(timezone.utc),
    )


def _make_methodology_revision(
    *,
    template_id: UUID,
    version: int,
    role_id: UUID,
    role_version: int = 1,
) -> MethodologyRevision:
    return MethodologyRevision(
        id=uuid4(),
        methodology_template_id=template_id,
        version=version,
        role_refs=(
            RoleRef(role_id=role_id, role_version=role_version),
        ),
        created_by_user_id="cli-operator",
        created_at=datetime.now(timezone.utc),
        previous_revision_hash=GENESIS_REVISION_HASH,
        this_revision_hash="a" * 64,
    )


def _make_role_template(*, template_id: UUID) -> RoleTemplate:
    return RoleTemplate(
        id=template_id,
        name="LVTGuide",
        description="LVT guide role",
        created_by_user_id="cli-operator",
        created_at=datetime.now(timezone.utc),
    )


def _make_role_revision(
    *,
    template_id: UUID,
    version: int = 1,
    top_k: int = 8,
) -> RoleRevision:
    return RoleRevision(
        id=uuid4(),
        role_template_id=template_id,
        version=version,
        system_prompt="You are an LVT assistant.",
        source_ids=(),
        tool_allowlist=(),
        retrieval_strategy={"strategy": "hybrid", "params": {}},
        filter_tree={"node": {}},
        top_k=top_k,
        min_score=Decimal("0.3"),
        model_selection="qwen2.5:7b",
        created_by_user_id="cli-operator",
        created_at=datetime.now(timezone.utc),
        previous_revision_hash=GENESIS_REVISION_HASH,
        this_revision_hash="b" * 64,
    )


class _FakeMethodologyRepository:
    def __init__(self) -> None:
        self.templates: dict[UUID, MethodologyTemplate] = {}
        self.revisions: dict[UUID, list[MethodologyRevision]] = {}
        self.calls: list[tuple[str, dict]] = []

    async def get_template(
        self,
        template_id: UUID,
        version: int | None = None,
    ) -> tuple[MethodologyTemplate, MethodologyRevision]:
        self.calls.append(("get_template", {"template_id": template_id, "version": version}))
        if template_id not in self.templates:
            raise LookupError(f"methodology template {template_id} not found")
        revs = self.revisions[template_id]
        if version is None:
            return self.templates[template_id], revs[-1]
        for r in revs:
            if r.version == version:
                return self.templates[template_id], r
        raise LookupError(
            f"methodology template {template_id} version {version} not found"
        )

    async def create_template(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("lookup adapter never writes")

    async def list_templates(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("lookup adapter never lists")

    async def add_revision(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("lookup adapter never adds revisions")

    async def archive_template(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("lookup adapter never archives")


class _FakeRoleRepository:
    def __init__(self) -> None:
        self.templates: dict[UUID, RoleTemplate] = {}
        self.revisions: dict[UUID, list[RoleRevision]] = {}
        self.calls: list[tuple[str, dict]] = []

    async def get_template(
        self,
        template_id: UUID,
        version: int | None = None,
    ) -> tuple[RoleTemplate, RoleRevision]:
        self.calls.append(("get_template", {"template_id": template_id, "version": version}))
        if template_id not in self.templates:
            raise LookupError(f"role template {template_id} not found")
        revs = self.revisions[template_id]
        if version is None:
            return self.templates[template_id], revs[-1]
        for r in revs:
            if r.version == version:
                return self.templates[template_id], r
        raise LookupError(f"role template {template_id} version {version} not found")

    async def create_template(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("lookup adapter never writes")

    async def list_templates(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("lookup adapter never lists")

    async def add_revision(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("lookup adapter never adds revisions")

    async def archive_template(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("lookup adapter never archives")


class _FakeSourceRepository:
    def __init__(self, sources: list[Source] | None = None) -> None:
        self._sources = sources or []
        self.calls: list[tuple[UUID, str]] = []

    async def get_source(self, source_id: UUID, tenant_id: str) -> Source | None:
        self.calls.append((source_id, tenant_id))
        for s in self._sources:
            if s.id == source_id and s.tenant_id == tenant_id:
                return s
        return None


def _make_source(*, source_id: UUID, tenant_id: str) -> Source:
    now = datetime.now(timezone.utc)
    return Source(
        id=source_id,
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        file_name="test.md",
        file_type="markdown",
        file_size_bytes=10,
        raw_content=b"# test\n\n",
        state=SourceState.RECEIVED,
        parsing_error_text=None,
        created_by_user_id="user-1",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture(scope="module")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


def _wire_lookup_repos(
    *,
    methodology_template_id: UUID,
    methodology_versions: list[int],
    role_template_id: UUID,
    role_top_k: int = 8,
    methodology_description: str | None = "LVT methodology",
) -> tuple[_FakeMethodologyRepository, _FakeRoleRepository]:
    methodology_repo = _FakeMethodologyRepository()
    methodology_repo.templates[methodology_template_id] = _make_methodology_template(
        template_id=methodology_template_id, description=methodology_description
    )
    methodology_repo.revisions[methodology_template_id] = [
        _make_methodology_revision(
            template_id=methodology_template_id,
            version=v,
            role_id=role_template_id,
        )
        for v in methodology_versions
    ]

    role_repo = _FakeRoleRepository()
    role_repo.templates[role_template_id] = _make_role_template(
        template_id=role_template_id
    )
    role_repo.revisions[role_template_id] = [
        _make_role_revision(template_id=role_template_id, version=1, top_k=role_top_k)
    ]
    return methodology_repo, role_repo


# ---------------------------------------------------------------------
# MethodologyLookupAdapter (resolves methodology + role per D86)
# ---------------------------------------------------------------------


def test_methodology_adapter_resolves_role_and_assembles_view(event_loop) -> None:
    """Happy path: the adapter joins methodology revision + role revision
    via role_refs[0] and populates MethodologyView with the role's bundle."""
    methodology_template_id = uuid4()
    role_template_id = uuid4()
    methodology_repo, role_repo = _wire_lookup_repos(
        methodology_template_id=methodology_template_id,
        methodology_versions=[1],
        role_template_id=role_template_id,
        role_top_k=8,
    )
    adapter = MethodologyLookupAdapter(
        methodology_repository=methodology_repo,
        role_repository=role_repo,
    )

    view = event_loop.run_until_complete(
        adapter(
            template_id=methodology_template_id,
            version=1,
            principal=_operator_principal(),
        )
    )

    assert isinstance(view, MethodologyView)
    assert view.methodology_template_id == methodology_template_id
    assert view.methodology_version == 1
    # D86: the adapter records the resolved role's id and version on
    # the view so create_agent_from_methodology populates both lineage
    # pairs without a second cross-context hop.
    assert view.role_id == role_template_id
    assert view.role_version == 1
    assert view.description == "LVT methodology"
    assert view.system_prompt == "You are an LVT assistant."
    assert view.tool_allowlist == ()
    assert view.retrieval_strategy == {"strategy": "hybrid", "params": {}}
    assert view.filter_tree == {"node": {}}
    assert view.top_k == 8
    assert view.min_score == Decimal("0.3")
    assert view.model_selection == "qwen2.5:7b"

    # Adapter called both repositories.
    assert any(c[0] == "get_template" for c in methodology_repo.calls)
    assert any(c[0] == "get_template" for c in role_repo.calls)


def test_methodology_adapter_resolves_version_none_to_latest(event_loop) -> None:
    """version=None passes through; the adapter records the resolved
    integer in methodology_version so the consumer never sees None."""
    methodology_template_id = uuid4()
    role_template_id = uuid4()
    methodology_repo, role_repo = _wire_lookup_repos(
        methodology_template_id=methodology_template_id,
        methodology_versions=[1, 2, 3],
        role_template_id=role_template_id,
        role_top_k=12,
    )
    adapter = MethodologyLookupAdapter(
        methodology_repository=methodology_repo,
        role_repository=role_repo,
    )

    view = event_loop.run_until_complete(
        adapter(
            template_id=methodology_template_id,
            version=None,
            principal=_operator_principal(),
        )
    )

    assert view.methodology_version == 3
    assert view.top_k == 12  # role's content surfaces through the view
    assert methodology_repo.calls[0] == (
        "get_template",
        {"template_id": methodology_template_id, "version": None},
    )


def test_methodology_adapter_threads_principal_to_use_case(event_loop) -> None:
    """The adapter passes the consumer's principal through to both
    get_methodology_template and get_role_template. Structural-typing
    satisfaction is the load-bearing assertion."""
    methodology_template_id = uuid4()
    role_template_id = uuid4()
    methodology_repo, role_repo = _wire_lookup_repos(
        methodology_template_id=methodology_template_id,
        methodology_versions=[1],
        role_template_id=role_template_id,
    )
    adapter = MethodologyLookupAdapter(
        methodology_repository=methodology_repo,
        role_repository=role_repo,
    )
    principal = _operator_principal()

    view = event_loop.run_until_complete(
        adapter(
            template_id=methodology_template_id,
            version=1,
            principal=principal,
        )
    )

    assert view.methodology_template_id == methodology_template_id


def test_methodology_adapter_raises_when_role_refs_empty(event_loop) -> None:
    """The adapter must reject methodology revisions with empty
    role_refs because the resolution target is undefined."""
    methodology_template_id = uuid4()
    role_template_id = uuid4()
    methodology_repo = _FakeMethodologyRepository()
    methodology_repo.templates[methodology_template_id] = _make_methodology_template(
        template_id=methodology_template_id, description="empty role_refs"
    )
    methodology_repo.revisions[methodology_template_id] = [
        MethodologyRevision(
            id=uuid4(),
            methodology_template_id=methodology_template_id,
            version=1,
            role_refs=(),
            created_by_user_id="cli-operator",
            created_at=datetime.now(timezone.utc),
            previous_revision_hash=GENESIS_REVISION_HASH,
            this_revision_hash="c" * 64,
        )
    ]
    role_repo = _FakeRoleRepository()
    adapter = MethodologyLookupAdapter(
        methodology_repository=methodology_repo,
        role_repository=role_repo,
    )

    with pytest.raises(LookupError):
        event_loop.run_until_complete(
            adapter(
                template_id=methodology_template_id,
                version=1,
                principal=_operator_principal(),
            )
        )


# ---------------------------------------------------------------------
# SourceLookupAdapter (unchanged at S26a-1)
# ---------------------------------------------------------------------


def test_source_adapter_returns_silently_when_all_sources_exist(
    event_loop,
) -> None:
    a = uuid4()
    b = uuid4()
    c = uuid4()
    repo = _FakeSourceRepository(
        [
            _make_source(source_id=a, tenant_id=_TENANT_A_UUID),
            _make_source(source_id=b, tenant_id=_TENANT_A_UUID),
            _make_source(source_id=c, tenant_id=_TENANT_A_UUID),
        ]
    )
    adapter = SourceLookupAdapter(repository=repo)

    event_loop.run_until_complete(
        adapter.assert_sources_exist(
            source_ids=(a, b, c),
            tenant_context=_tenant_context(),
            principal=_operator_principal(),
        )
    )

    assert {sid for sid, _ in repo.calls} == {a, b, c}
    assert {tenant for _, tenant in repo.calls} == {_TENANT_A_UUID}


def test_source_adapter_raises_source_not_found_with_offending_ids(
    event_loop,
) -> None:
    a = uuid4()
    b_missing = uuid4()
    c = uuid4()
    d_missing = uuid4()
    repo = _FakeSourceRepository(
        [
            _make_source(source_id=a, tenant_id=_TENANT_A_UUID),
            _make_source(source_id=c, tenant_id=_TENANT_A_UUID),
        ]
    )
    adapter = SourceLookupAdapter(repository=repo)

    with pytest.raises(SourceNotFoundError) as exc_info:
        event_loop.run_until_complete(
            adapter.assert_sources_exist(
                source_ids=(a, b_missing, c, d_missing),
                tenant_context=_tenant_context(),
                principal=_operator_principal(),
            )
        )

    assert set(exc_info.value.missing_source_ids) == {b_missing, d_missing}


def test_source_adapter_treats_cross_tenant_source_as_missing(event_loop) -> None:
    sid = uuid4()
    other_tenant = "00000000-0000-4000-8000-00000000b002"
    repo = _FakeSourceRepository(
        [_make_source(source_id=sid, tenant_id=other_tenant)]
    )
    adapter = SourceLookupAdapter(repository=repo)

    with pytest.raises(SourceNotFoundError) as exc_info:
        event_loop.run_until_complete(
            adapter.assert_sources_exist(
                source_ids=(sid,),
                tenant_context=_tenant_context(),
                principal=_operator_principal(),
            )
        )

    assert exc_info.value.missing_source_ids == (sid,)
    assert repo.calls == [(sid, _TENANT_A_UUID)]


# ---------------------------------------------------------------------
# RoleLookupAdapter (S26a-2 / D86)
# ---------------------------------------------------------------------


def test_role_adapter_resolves_role_template_and_assembles_view(event_loop) -> None:
    """Happy path: the adapter calls get_role_template and translates
    the producer's (RoleTemplate, RoleRevision) tuple into a
    consumer-shaped RoleView."""
    role_template_id = uuid4()
    role_repo = _FakeRoleRepository()
    role_repo.templates[role_template_id] = _make_role_template(
        template_id=role_template_id
    )
    role_repo.revisions[role_template_id] = [
        _make_role_revision(template_id=role_template_id, version=1, top_k=8)
    ]
    adapter = RoleLookupAdapter(role_repository=role_repo)

    view = event_loop.run_until_complete(
        adapter(
            role_id=role_template_id,
            version=1,
            principal=_operator_principal(),
        )
    )

    assert isinstance(view, RoleView)
    assert view.role_id == role_template_id
    assert view.role_version == 1
    assert view.description == "LVT guide role"
    assert view.system_prompt == "You are an LVT assistant."
    assert view.top_k == 8
    assert view.min_score == Decimal("0.3")
    assert view.model_selection == "qwen2.5:7b"

    assert any(c[0] == "get_template" for c in role_repo.calls)


def test_role_adapter_resolves_version_none_to_latest(event_loop) -> None:
    """version=None passes through; the adapter records the resolved
    integer in role_version so the consumer never sees None."""
    role_template_id = uuid4()
    role_repo = _FakeRoleRepository()
    role_repo.templates[role_template_id] = _make_role_template(
        template_id=role_template_id
    )
    role_repo.revisions[role_template_id] = [
        _make_role_revision(template_id=role_template_id, version=1, top_k=8),
        _make_role_revision(template_id=role_template_id, version=2, top_k=12),
    ]
    adapter = RoleLookupAdapter(role_repository=role_repo)

    view = event_loop.run_until_complete(
        adapter(
            role_id=role_template_id,
            version=None,
            principal=_operator_principal(),
        )
    )

    assert view.role_version == 2
    assert view.top_k == 12


def test_role_adapter_propagates_lookup_error(event_loop) -> None:
    """Missing role raises LookupError from the repository; the adapter
    lets it propagate without re-wrapping."""
    role_repo = _FakeRoleRepository()
    adapter = RoleLookupAdapter(role_repository=role_repo)

    with pytest.raises(LookupError):
        event_loop.run_until_complete(
            adapter(
                role_id=uuid4(),
                version=None,
                principal=_operator_principal(),
            )
        )


# ----------------------------------------------------------------------
# AgentRetrievalClientAdapter + MethodologyOverridesLookupAdapter
# (S27b / D88)
# ----------------------------------------------------------------------


class _FakeIngestionRetrievalClient:
    """Fake implementing the ingestion RetrievalClient surface."""

    def __init__(self) -> None:
        self.vector_calls: list[dict] = []
        self.graph_calls: list[dict] = []
        self._vector_results: list = []
        self._graph_results: list = []

    def stub_vector(self, results) -> None:
        self._vector_results = list(results)

    def stub_graph(self, results) -> None:
        self._graph_results = list(results)

    async def search_vector(self, *, query, scope, limit):
        self.vector_calls.append(
            {"query": query, "scope": scope, "limit": limit}
        )
        return list(self._vector_results)

    async def traverse_graph(self, *, seed, scope, depth):
        self.graph_calls.append(
            {"seed": seed, "scope": scope, "depth": depth}
        )
        return list(self._graph_results)


def _make_chunk_result(*, content: str, score: float, source_id: UUID | None = None):
    """Construct a ChunkResult mirroring ingestion's domain shape."""
    from contexts.ingestion.domain.chunk_result import ChunkResult

    return ChunkResult(
        chunk_id=uuid4(),
        source_id=source_id or uuid4(),
        tenant_id=_TENANT_A_UUID,
        jurisdiction="eu-west",
        content=content,
        structural_metadata={},
        similarity_score=score,
        created_at=datetime.now(timezone.utc),
    )


def test_agent_retrieval_adapter_vector_primary_filters_by_min_score(event_loop) -> None:
    """Vector dispatch passes top_k to search_vector; min_score post-filters."""
    ingestion = _FakeIngestionRetrievalClient()
    ingestion.stub_vector(
        [
            _make_chunk_result(content="high relevance", score=0.91),
            _make_chunk_result(content="medium relevance", score=0.55),
            _make_chunk_result(content="below floor", score=0.32),
        ]
    )
    adapter = AgentRetrievalClientAdapter(retrieval_client=ingestion)

    result = event_loop.run_until_complete(
        adapter(
            query="what is LVT",
            tenant_context=_tenant_context(),
            retrieval_strategy={"primary": "vector"},
            filter_tree={},
            top_k=5,
            min_score=Decimal("0.5"),
        )
    )

    assert ingestion.vector_calls == [
        {"query": "what is LVT", "scope": _tenant_context(), "limit": 5}
    ]
    # Three raw results; min_score=0.5 admits the 0.91 and 0.55 chunks.
    assert len(result) == 2
    assert result[0].text == "high relevance"
    assert result[0].score == 0.91
    assert result[1].text == "medium relevance"


def test_agent_retrieval_adapter_unknown_strategy_returns_empty(event_loop) -> None:
    ingestion = _FakeIngestionRetrievalClient()
    adapter = AgentRetrievalClientAdapter(retrieval_client=ingestion)

    result = event_loop.run_until_complete(
        adapter(
            query="x",
            tenant_context=_tenant_context(),
            retrieval_strategy={"primary": "frobnicate"},
            filter_tree={},
            top_k=5,
            min_score=Decimal("0"),
        )
    )

    assert result == ()
    assert ingestion.vector_calls == []
    assert ingestion.graph_calls == []


def test_agent_retrieval_adapter_zero_results_returns_empty_tuple(event_loop) -> None:
    """A no-match search returns an empty tuple, which the executor
    formats as the no-chunks-matched tool-result marker."""
    ingestion = _FakeIngestionRetrievalClient()
    ingestion.stub_vector([])
    adapter = AgentRetrievalClientAdapter(retrieval_client=ingestion)

    result = event_loop.run_until_complete(
        adapter(
            query="nothing matches",
            tenant_context=_tenant_context(),
            retrieval_strategy={"primary": "vector"},
            filter_tree={},
            top_k=10,
            min_score=Decimal("0.5"),
        )
    )

    assert result == ()


def test_methodology_overrides_adapter_returns_matching_role_overrides(event_loop) -> None:
    """For a methodology revision with role_refs carrying overrides,
    the adapter returns the overrides for the matching role_id."""
    methodology_id = uuid4()
    role_id = uuid4()
    other_role_id = uuid4()
    repo = _FakeMethodologyRepository()
    repo.templates[methodology_id] = _make_methodology_template(
        template_id=methodology_id, description="McKinsey 7-Step"
    )
    revision = MethodologyRevision(
        id=uuid4(),
        methodology_template_id=methodology_id,
        version=1,
        role_refs=(
            RoleRef(
                role_id=other_role_id,
                role_version=1,
                overrides={
                    "system_prompt": {
                        "mode": "augment",
                        "value": "Apply MECE decomposition.",
                    },
                },
            ),
            RoleRef(
                role_id=role_id,
                role_version=1,
                overrides={
                    "system_prompt": {
                        "mode": "augment",
                        "value": "Apply the SCQ framework.",
                    },
                },
            ),
        ),
        created_by_user_id="cli-operator",
        created_at=datetime.now(timezone.utc),
        previous_revision_hash=GENESIS_REVISION_HASH,
        this_revision_hash="m" * 64,
    )
    repo.revisions[methodology_id] = [revision]
    adapter = MethodologyOverridesLookupAdapter(methodology_repository=repo)

    overrides = event_loop.run_until_complete(
        adapter(
            methodology_template_id=methodology_id,
            methodology_version=1,
            role_id=role_id,
            principal=_operator_principal(),
        )
    )

    assert overrides == {
        "system_prompt": {
            "mode": "augment",
            "value": "Apply the SCQ framework.",
        },
    }


def test_methodology_overrides_adapter_returns_empty_when_no_matching_role(event_loop) -> None:
    """When the methodology revision has no role_refs entry for the
    given role_id, the adapter returns an empty dict (no overrides)."""
    methodology_id = uuid4()
    role_id = uuid4()
    different_role_id = uuid4()
    repo = _FakeMethodologyRepository()
    repo.templates[methodology_id] = _make_methodology_template(
        template_id=methodology_id, description="LVT"
    )
    repo.revisions[methodology_id] = [
        _make_methodology_revision(
            template_id=methodology_id,
            version=1,
            role_id=different_role_id,
        ),
    ]
    adapter = MethodologyOverridesLookupAdapter(methodology_repository=repo)

    overrides = event_loop.run_until_complete(
        adapter(
            methodology_template_id=methodology_id,
            methodology_version=1,
            role_id=role_id,
            principal=_operator_principal(),
        )
    )

    assert overrides == {}


def test_methodology_overrides_adapter_propagates_lookup_error(event_loop) -> None:
    repo = _FakeMethodologyRepository()
    adapter = MethodologyOverridesLookupAdapter(methodology_repository=repo)

    with pytest.raises(LookupError):
        event_loop.run_until_complete(
            adapter(
                methodology_template_id=uuid4(),
                methodology_version=None,
                role_id=uuid4(),
                principal=_operator_principal(),
            )
        )
