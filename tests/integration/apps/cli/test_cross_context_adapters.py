"""Integration tests for the apps/cli cross-context adapters (S25 / D79).

Exercises MethodologyLookupAdapter and SourceLookupAdapter through
the real producer-side application use cases
(``get_methodology_template`` from methodology;
``get_source`` from ingestion) against in-memory fake repositories.
The integration scope here is "adapter + real producer use case +
in-memory repo" — the database layer is tested by the methodology
and ingestion adapter integration suites; the e2e against the full
live stack lands at commit 10.

Six tests covering the brief's named scope: methodology adapter
translation, version=None passthrough, principal threading, source
adapter happy path, source adapter missing-source error path, and
source adapter tenant-context routing.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from apps.cli._cross_context import (
    MethodologyLookupAdapter,
    SourceLookupAdapter,
)
from contexts.agent.application.ports import (
    MethodologyView,
    SourceNotFoundError,
)
from contexts.ingestion.domain.source import Source
from contexts.ingestion.domain.state import SourceState
from contexts.methodology.domain.methodology import (
    MethodologyRevision,
    MethodologyTemplate,
)
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


def _make_template(*, template_id: UUID, description: str | None) -> MethodologyTemplate:
    return MethodologyTemplate(
        id=template_id,
        name="LVT",
        description=description,
        created_by_user_id="cli-operator",
        created_at=datetime.now(timezone.utc),
    )


def _make_revision(
    *,
    template_id: UUID,
    version: int,
    top_k: int = 8,
) -> MethodologyRevision:
    return MethodologyRevision(
        id=uuid4(),
        methodology_template_id=template_id,
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
        this_revision_hash="a" * 64,
    )


class _FakeMethodologyRepository:
    """In-memory MethodologyRepositoryPort fake.

    Exposes get_template returning a template plus the named or
    latest revision; the methodology use case ``get_methodology_template``
    calls through this directly so the real use case logic is
    exercised end-to-end.
    """

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

    # Methods unused by the lookup but present so the type-checker is
    # satisfied if a future test reuses this fake.
    async def create_template(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("lookup adapter never writes")

    async def list_templates(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("lookup adapter never lists")

    async def add_revision(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("lookup adapter never adds revisions")

    async def archive_template(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("lookup adapter never archives")


class _FakeSourceRepository:
    """In-memory SourceRepositoryPort fake.

    Implements only the methods get_source touches; the adapter's
    per-id call sequence reaches into this through the real
    ``contexts.ingestion.application.get_source`` use case so the
    None-to-LookupError upgrade is exercised end-to-end.
    """

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


# ---------------------------------------------------------------------
# MethodologyLookupAdapter
# ---------------------------------------------------------------------


def test_methodology_adapter_translates_template_and_revision_to_view(
    event_loop,
) -> None:
    """Happy path: the adapter receives the (Template, Revision)
    tuple from get_methodology_template and assembles a
    MethodologyView with the consumer-shaped field set."""
    repo = _FakeMethodologyRepository()
    template_id = uuid4()
    repo.templates[template_id] = _make_template(
        template_id=template_id, description="LVT methodology"
    )
    repo.revisions[template_id] = [
        _make_revision(template_id=template_id, version=1, top_k=8)
    ]
    adapter = MethodologyLookupAdapter(repository=repo)

    view = event_loop.run_until_complete(
        adapter(
            template_id=template_id,
            version=1,
            principal=_operator_principal(),
        )
    )

    assert isinstance(view, MethodologyView)
    assert view.methodology_template_id == template_id
    assert view.methodology_version == 1
    assert view.description == "LVT methodology"
    assert view.system_prompt == "You are an LVT assistant."
    assert view.tool_allowlist == ()
    assert view.retrieval_strategy == {"strategy": "hybrid", "params": {}}
    assert view.filter_tree == {"node": {}}
    assert view.top_k == 8
    assert view.min_score == Decimal("0.3")
    assert view.model_selection == "qwen2.5:7b"


def test_methodology_adapter_resolves_version_none_to_latest(event_loop) -> None:
    """version=None passes through to the underlying repository which
    returns the latest revision; the adapter records the resolved
    integer in the returned view's methodology_version so the
    consumer never sees None."""
    repo = _FakeMethodologyRepository()
    template_id = uuid4()
    repo.templates[template_id] = _make_template(
        template_id=template_id, description=None
    )
    repo.revisions[template_id] = [
        _make_revision(template_id=template_id, version=1, top_k=5),
        _make_revision(template_id=template_id, version=2, top_k=7),
        _make_revision(template_id=template_id, version=3, top_k=12),
    ]
    adapter = MethodologyLookupAdapter(repository=repo)

    view = event_loop.run_until_complete(
        adapter(
            template_id=template_id,
            version=None,
            principal=_operator_principal(),
        )
    )

    assert view.methodology_version == 3
    assert view.top_k == 12  # latest revision's content
    # Adapter forwarded version=None to repository.
    assert repo.calls[0] == ("get_template", {"template_id": template_id, "version": None})


def test_methodology_adapter_threads_principal_to_use_case(event_loop) -> None:
    """The adapter passes the consumer's principal through to
    get_methodology_template. The fake repository doesn't see the
    principal (use case doesn't pass it to the repo for methodology
    reads per D74), but the adapter's call into the use case has the
    principal as a named kwarg so any future use case logic
    referencing it works.

    This test asserts that no exception is raised when a real
    Principal flows through; the structural-typing satisfaction is
    the load-bearing assertion."""
    repo = _FakeMethodologyRepository()
    template_id = uuid4()
    repo.templates[template_id] = _make_template(
        template_id=template_id, description=None
    )
    repo.revisions[template_id] = [
        _make_revision(template_id=template_id, version=1)
    ]
    adapter = MethodologyLookupAdapter(repository=repo)
    principal = _operator_principal()

    view = event_loop.run_until_complete(
        adapter(
            template_id=template_id,
            version=1,
            principal=principal,
        )
    )

    assert view.methodology_template_id == template_id


# ---------------------------------------------------------------------
# SourceLookupAdapter
# ---------------------------------------------------------------------


def test_source_adapter_returns_silently_when_all_sources_exist(
    event_loop,
) -> None:
    """Happy path: every requested source resolves; assert_sources_exist
    completes without raising."""
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

    # Adapter called the repo per id with the routed tenant.
    assert {sid for sid, _ in repo.calls} == {a, b, c}
    assert {tenant for _, tenant in repo.calls} == {_TENANT_A_UUID}


def test_source_adapter_raises_source_not_found_with_offending_ids(
    event_loop,
) -> None:
    """Missing-source path: the adapter accumulates offending ids
    and surfaces a single SourceNotFoundError with all of them."""
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
    """Tenant-context routing: a source that exists for tenant B is
    treated as missing for tenant A. D24 tenant isolation makes
    cross-tenant access structurally indistinguishable from missing-
    id, which is the documented expectation in source_lookup.py."""
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
    # Adapter called the repo with tenant_a (the routed tenant), not
    # the source's actual tenant.
    assert repo.calls == [(sid, _TENANT_A_UUID)]
