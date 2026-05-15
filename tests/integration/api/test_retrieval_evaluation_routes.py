"""Integration tests for the retrieval-evaluation HTTP routes (D112, S42).

Uses FastAPI TestClient with dependency_overrides per the established
pattern at test_run_history_routes.py / test_audit_routes.py. The
reader, repository, audit port, and retrieval-client / runner-port
dependencies are substituted via the ``get_*`` accessors declared in
``apps/api/routers/retrieval_evaluation.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Sequence
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.main import AppCompositions, create_app
from apps.api.routers.inference import get_tenant_context
from apps.api.routers.retrieval_evaluation import (
    get_audit_port,
    get_evaluation_run_reader,
    get_evaluation_run_repository,
    get_gold_set_reader,
    get_gold_set_repository,
    get_retrieval_client,
    get_retrieval_runner_port,
)
from contexts.audit.domain.events import AuditEvent
from contexts.ingestion.domain.chunk_result import ChunkResult
from contexts.retrieval_evaluation.domain import (
    EvaluationAggregate,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunStatus,
    GoldSet,
    GoldSetEntry,
    GoldSetRevision,
    GoldSetRevisionStatus,
)
from contexts.retrieval_evaluation.domain.query_filters import (
    EvaluationRunListCursor,
    GoldSetListCursor,
)
from contexts.retrieval_evaluation.ports.evaluation_run_reader import (
    EvaluationRunListPage,
    EvaluationRunSnapshot,
)
from contexts.retrieval_evaluation.ports.reader import (
    GoldSetListPage,
    GoldSetWithCurrentRevision,
    RevisionWithEntries,
)
from contexts.retrieval_evaluation.ports.retrieval_runner import RankedChunks
from padhanam.events import SynchronousEventBus
from padhanam.security.auth import issue_dev_token
from shared_kernel import TenantContext


_TENANT_UUID = "00000000-0000-4000-8000-0000000000a1"
_TENANT_UUID_AS_UUID = UUID(_TENANT_UUID)
_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc)


def _tenant_context_fixture() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_UUID,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_UUID,
    )


def _token() -> str:
    return issue_dev_token(
        subject="alice",
        tenant_id=_TENANT_UUID,
        roles=["agent.invoke"],
    )


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeGoldSetRepository:
    def __init__(self) -> None:
        self.persisted: list[tuple[GoldSet, GoldSetRevision]] = []
        self.opened_drafts: list[GoldSetRevision] = []
        self.appended: list[GoldSetEntry] = []
        self.finalized: list[dict[str, Any]] = []

    async def persist_new_gold_set(
        self, *, tenant_context: TenantContext, gold_set: GoldSet,
        initial_revision: GoldSetRevision,
    ) -> None:
        self.persisted.append((gold_set, initial_revision))

    async def open_new_draft_revision(
        self, *, tenant_context: TenantContext, revision: GoldSetRevision,
    ) -> None:
        self.opened_drafts.append(revision)

    async def append_entry(
        self, *, tenant_context: TenantContext, entry: GoldSetEntry,
    ) -> None:
        self.appended.append(entry)

    async def finalize_revision(
        self,
        *,
        tenant_context: TenantContext,
        revision_id: UUID,
        gold_set_id: UUID,
        this_event_hash: str,
        previous_event_hash: str,
        finalized_at: datetime,
    ) -> None:
        self.finalized.append(
            {
                "revision_id": revision_id,
                "gold_set_id": gold_set_id,
                "this_event_hash": this_event_hash,
                "previous_event_hash": previous_event_hash,
                "finalized_at": finalized_at,
            }
        )


class _FakeGoldSetReader:
    def __init__(self) -> None:
        self.list_returns = GoldSetListPage(gold_sets=(), next_cursor=None)
        self.get_returns: GoldSetWithCurrentRevision | None = None
        self.draft_returns: GoldSetRevision | None = None
        self.revision_with_entries_returns: RevisionWithEntries | None = None
        self.list_calls: list[
            tuple[TenantContext, GoldSetListCursor | None, int]
        ] = []
        self.get_calls: list[tuple[TenantContext, UUID]] = []

    async def list_gold_sets(
        self,
        *,
        tenant_context: TenantContext,
        cursor: GoldSetListCursor | None,
        page_size: int,
    ) -> GoldSetListPage:
        self.list_calls.append((tenant_context, cursor, page_size))
        return self.list_returns

    async def get_gold_set_with_current_revision(
        self, *, tenant_context: TenantContext, gold_set_id: UUID,
    ) -> GoldSetWithCurrentRevision | None:
        self.get_calls.append((tenant_context, gold_set_id))
        return self.get_returns

    async def get_revision_with_entries(
        self, *, tenant_context: TenantContext, revision_id: UUID,
    ) -> RevisionWithEntries | None:
        return self.revision_with_entries_returns

    async def find_current_draft_revision(
        self, *, tenant_context: TenantContext, gold_set_id: UUID,
    ) -> GoldSetRevision | None:
        return self.draft_returns


class _FakeEvaluationRunRepository:
    def __init__(self) -> None:
        self.runs: list[EvaluationRun] = []
        self.results: list[EvaluationResult] = []
        self.aggregates: list[EvaluationAggregate] = []
        self.completed: list[UUID] = []
        self.failed: list[UUID] = []

    async def persist_run(self, *, tenant_context, run):
        self.runs.append(run)

    async def persist_result(self, *, tenant_context, result):
        self.results.append(result)

    async def persist_aggregate(self, *, tenant_context, aggregate):
        self.aggregates.append(aggregate)

    async def mark_completed(self, *, tenant_context, run_id, completed_at):
        self.completed.append(run_id)

    async def mark_failed(self, *, tenant_context, run_id, completed_at):
        self.failed.append(run_id)


class _FakeEvaluationRunReader:
    def __init__(self) -> None:
        self.snapshot_returns: EvaluationRunSnapshot | None = None
        self.list_returns = EvaluationRunListPage(runs=(), next_cursor=None)

    async def list_runs(
        self,
        *,
        tenant_context: TenantContext,
        cursor: EvaluationRunListCursor | None,
        page_size: int,
    ) -> EvaluationRunListPage:
        return self.list_returns

    async def get_run_with_results_and_aggregates(
        self, *, tenant_context: TenantContext, run_id: UUID,
    ) -> EvaluationRunSnapshot | None:
        return self.snapshot_returns


class _FakeAuditPort:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def emit(self, event: AuditEvent) -> None:
        self.events.append(event)


class _FakeRetrievalClient:
    def __init__(self) -> None:
        self.returns: Sequence[ChunkResult] = ()
        self.calls: list[tuple[str, TenantContext, int]] = []

    async def search_vector(
        self, *, query: str, scope: TenantContext, limit: int,
    ) -> Sequence[ChunkResult]:
        self.calls.append((query, scope, limit))
        return self.returns

    async def search_vector_positional(
        self, query: str, scope: TenantContext, limit: int,
    ) -> Sequence[ChunkResult]:
        return await self.search_vector(query=query, scope=scope, limit=limit)


# Backwards-compat: the route handler calls
# ``retrieval_client.search_vector(query=..., scope=..., limit=...)``.
# Keep the API positional-or-kwarg agnostic via the kwarg call above.


class _FakeRetrievalRunnerPort:
    """Implements ``RetrievalRunnerPort`` returning empty RankedChunks per call.

    Used by the synchronous evaluation-run kickoff route. Per
    ``BinaryRelevanceMetrics`` the empty-chunk path produces all-zero
    metrics which satisfy the EvaluationResult invariants.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(
        self, *, query: str, tenant_context: TenantContext,
        strategy_dispatch, top_k: int,
    ) -> RankedChunks:
        self.calls.append(
            {
                "query": query,
                "tenant_context": tenant_context,
                "strategy_dispatch": strategy_dispatch,
                "top_k": top_k,
            }
        )
        return RankedChunks(chunk_ids=(), latency_ms=5)


# ---------------------------------------------------------------------------
# App builder
# ---------------------------------------------------------------------------


def _build_app(
    *,
    gold_set_repository: _FakeGoldSetRepository | None = None,
    gold_set_reader: _FakeGoldSetReader | None = None,
    evaluation_run_repository: _FakeEvaluationRunRepository | None = None,
    evaluation_run_reader: _FakeEvaluationRunReader | None = None,
    audit_port: _FakeAuditPort | None = None,
    retrieval_client: _FakeRetrievalClient | None = None,
    retrieval_runner_port: _FakeRetrievalRunnerPort | None = None,
) -> Any:
    class _StubInferencePort:
        def complete(self, messages, model, tenant_context, tools=()):
            raise AssertionError("inference path not exercised here")

    app = create_app(
        compositions=AppCompositions(
            inference_port=_StubInferencePort(),  # type: ignore[arg-type]
            event_bus=SynchronousEventBus(),
        ),
        configure_tracing=False,
    )
    app.include_router(
        __import__(
            "apps.api.routers.retrieval_evaluation", fromlist=["gold_set_router"]
        ).gold_set_router
    )
    app.include_router(
        __import__(
            "apps.api.routers.retrieval_evaluation", fromlist=["discovery_router"]
        ).discovery_router
    )
    app.include_router(
        __import__(
            "apps.api.routers.retrieval_evaluation",
            fromlist=["evaluation_run_router"],
        ).evaluation_run_router
    )
    app.dependency_overrides[get_tenant_context] = lambda: _tenant_context_fixture()
    if gold_set_repository is not None:
        app.dependency_overrides[get_gold_set_repository] = (
            lambda: gold_set_repository
        )
    if gold_set_reader is not None:
        app.dependency_overrides[get_gold_set_reader] = lambda: gold_set_reader
    if evaluation_run_repository is not None:
        app.dependency_overrides[get_evaluation_run_repository] = (
            lambda: evaluation_run_repository
        )
    if evaluation_run_reader is not None:
        app.dependency_overrides[get_evaluation_run_reader] = (
            lambda: evaluation_run_reader
        )
    if audit_port is not None:
        app.dependency_overrides[get_audit_port] = lambda: audit_port
    if retrieval_client is not None:
        app.dependency_overrides[get_retrieval_client] = lambda: retrieval_client
    if retrieval_runner_port is not None:
        app.dependency_overrides[get_retrieval_runner_port] = (
            lambda: retrieval_runner_port
        )
    # Register the retrieval_evaluation error handlers (the test harness
    # builds the app fresh, so the registration normally invoked by
    # create_app's _build_default_compositions path must fire here).
    from apps.api._errors import register_retrieval_evaluation_error_handlers
    register_retrieval_evaluation_error_handlers(app)
    return app


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_token()}"}


# ---------------------------------------------------------------------------
# POST /gold-sets
# ---------------------------------------------------------------------------


def test_create_gold_set_201_threads_principal_subject_to_actor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    repo = _FakeGoldSetRepository()
    app = _build_app(gold_set_repository=repo)
    client = TestClient(app)

    response = client.post(
        "/gold-sets",
        json={"name": "P11 retrieval baseline"},
        headers=_auth_headers(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["gold_set"]["name"] == "P11 retrieval baseline"
    assert body["initial_revision"]["status"] == "draft"
    assert body["initial_revision"]["revision_number"] == 1
    # Principal.subject from the JWT becomes created_by_user_id.
    gold_set, revision = repo.persisted[0]
    assert gold_set.created_by_user_id == "alice"
    assert revision.created_by_user_id == "alice"


def test_create_gold_set_rejects_empty_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    repo = _FakeGoldSetRepository()
    app = _build_app(gold_set_repository=repo)
    client = TestClient(app)
    response = client.post(
        "/gold-sets",
        json={"name": ""},
        headers=_auth_headers(),
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /gold-sets
# ---------------------------------------------------------------------------


def test_list_gold_sets_200_with_items(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    reader = _FakeGoldSetReader()
    gold_set = GoldSet(
        id=uuid4(), tenant_id=_TENANT_UUID_AS_UUID, jurisdiction="eu-west",
        name="P11 retrieval baseline", created_by_user_id="alice",
        created_at=_NOW, current_revision_id=uuid4(),
    )
    reader.list_returns = GoldSetListPage(
        gold_sets=(gold_set,), next_cursor=None
    )
    app = _build_app(gold_set_reader=reader)
    client = TestClient(app)

    response = client.get("/gold-sets?page_size=10", headers=_auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["name"] == "P11 retrieval baseline"
    assert body["next_cursor"] is None
    assert reader.list_calls[0][2] == 10  # page_size threaded through


def test_list_gold_sets_rejects_page_size_above_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    app = _build_app(gold_set_reader=_FakeGoldSetReader())
    client = TestClient(app)
    response = client.get("/gold-sets?page_size=999", headers=_auth_headers())
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /gold-sets/{id}
# ---------------------------------------------------------------------------


def test_get_gold_set_200_with_revision_and_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    reader = _FakeGoldSetReader()
    gold_set_id = uuid4()
    revision_id = uuid4()
    gold_set = GoldSet(
        id=gold_set_id, tenant_id=_TENANT_UUID_AS_UUID, jurisdiction="eu-west",
        name="P11 retrieval baseline", created_by_user_id="alice",
        created_at=_NOW, current_revision_id=revision_id,
    )
    revision = GoldSetRevision(
        id=revision_id, gold_set_id=gold_set_id, revision_number=1,
        status=GoldSetRevisionStatus.FINALIZED, created_by_user_id="alice",
        created_at=_NOW, finalized_at=_NOW,
        this_event_hash="a" * 64, previous_event_hash="0" * 64,
    )
    entry = GoldSetEntry(
        id=uuid4(), gold_set_revision_id=revision_id, entry_index=0,
        query="What is LVT?", expected_chunk_ids=(uuid4(),),
    )
    reader.get_returns = GoldSetWithCurrentRevision(
        gold_set=gold_set, current_revision=revision, entries=(entry,)
    )
    app = _build_app(gold_set_reader=reader)
    client = TestClient(app)

    response = client.get(f"/gold-sets/{gold_set_id}", headers=_auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["gold_set"]["id"] == str(gold_set_id)
    assert body["current_revision"]["this_event_hash"] == "a" * 64
    assert len(body["entries"]) == 1
    assert body["entries"][0]["query"] == "What is LVT?"


def test_get_gold_set_404_on_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    reader = _FakeGoldSetReader()
    reader.get_returns = None
    app = _build_app(gold_set_reader=reader)
    client = TestClient(app)

    response = client.get(f"/gold-sets/{uuid4()}", headers=_auth_headers())

    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "gold_set_not_found"
    assert body["correlation_id"]


# ---------------------------------------------------------------------------
# POST /gold-sets/{id}/entries
# ---------------------------------------------------------------------------


def test_append_entry_201_returns_revision_entry_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    repo = _FakeGoldSetRepository()
    reader = _FakeGoldSetReader()
    gold_set_id = uuid4()
    revision_id = uuid4()
    reader.draft_returns = GoldSetRevision(
        id=revision_id, gold_set_id=gold_set_id, revision_number=1,
        status=GoldSetRevisionStatus.DRAFT, created_by_user_id="alice",
        created_at=_NOW, finalized_at=None,
        this_event_hash=None, previous_event_hash=None,
    )
    reader.revision_with_entries_returns = RevisionWithEntries(
        revision=reader.draft_returns, entries=(),
    )
    chunk_a, chunk_b = uuid4(), uuid4()
    app = _build_app(gold_set_repository=repo, gold_set_reader=reader)
    client = TestClient(app)

    response = client.post(
        f"/gold-sets/{gold_set_id}/entries",
        json={
            "query": "What is LVT?",
            "expected_chunk_ids": [str(chunk_a), str(chunk_b)],
        },
        headers=_auth_headers(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["entry"]["query"] == "What is LVT?"
    assert body["entry"]["expected_chunk_ids"] == [str(chunk_a), str(chunk_b)]
    assert body["opened_new_draft"] is False
    assert repo.appended[0].expected_chunk_ids == (chunk_a, chunk_b)


def test_append_entry_404_on_missing_gold_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    repo = _FakeGoldSetRepository()
    reader = _FakeGoldSetReader()
    # No draft, no get_returns → GoldSetNotFoundError fires.
    reader.draft_returns = None
    reader.get_returns = None
    app = _build_app(gold_set_repository=repo, gold_set_reader=reader)
    client = TestClient(app)

    response = client.post(
        f"/gold-sets/{uuid4()}/entries",
        json={"query": "q", "expected_chunk_ids": [str(uuid4())]},
        headers=_auth_headers(),
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "gold_set_not_found"


# ---------------------------------------------------------------------------
# POST /gold-sets/{id}/finalize
# ---------------------------------------------------------------------------


def test_finalize_revision_409_when_no_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    repo = _FakeGoldSetRepository()
    reader = _FakeGoldSetReader()
    reader.draft_returns = None  # no current draft
    app = _build_app(gold_set_repository=repo, gold_set_reader=reader)
    client = TestClient(app)

    response = client.post(
        f"/gold-sets/{uuid4()}/finalize",
        headers=_auth_headers(),
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "no_draft_to_finalize"


def test_finalize_revision_400_when_empty_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    repo = _FakeGoldSetRepository()
    reader = _FakeGoldSetReader()
    gold_set_id = uuid4()
    revision_id = uuid4()
    reader.draft_returns = GoldSetRevision(
        id=revision_id, gold_set_id=gold_set_id, revision_number=1,
        status=GoldSetRevisionStatus.DRAFT, created_by_user_id="alice",
        created_at=_NOW, finalized_at=None,
        this_event_hash=None, previous_event_hash=None,
    )
    reader.revision_with_entries_returns = RevisionWithEntries(
        revision=reader.draft_returns, entries=(),  # empty entries → EmptyDraftError
    )
    app = _build_app(gold_set_repository=repo, gold_set_reader=reader)
    client = TestClient(app)

    response = client.post(
        f"/gold-sets/{gold_set_id}/finalize",
        headers=_auth_headers(),
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "empty_draft"


# ---------------------------------------------------------------------------
# GET /retrieval-candidates
# ---------------------------------------------------------------------------


def test_retrieval_candidates_200(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    client_fake = _FakeRetrievalClient()
    client_fake.returns = (
        ChunkResult(
            chunk_id=uuid4(), source_id=uuid4(), tenant_id=_TENANT_UUID,
            jurisdiction="eu-west", content="LVT excerpt",
            structural_metadata={}, similarity_score=0.91, created_at=_NOW,
            chunk_index=2, source_snapshot={"file_name": "lvt.md"},
        ),
    )
    app = _build_app(retrieval_client=client_fake)
    client = TestClient(app)

    response = client.get(
        "/retrieval-candidates?query=lvt&limit=5",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["candidates"]) == 1
    assert body["candidates"][0]["similarity_score"] == 0.91
    assert client_fake.calls[0][0] == "lvt"
    assert client_fake.calls[0][2] == 5


def test_retrieval_candidates_422_on_missing_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    client_fake = _FakeRetrievalClient()
    app = _build_app(retrieval_client=client_fake)
    client = TestClient(app)
    response = client.get("/retrieval-candidates", headers=_auth_headers())
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /evaluation-runs
# ---------------------------------------------------------------------------


def test_start_evaluation_run_synchronous_kickoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Synchronous kickoff returns completed snapshot in one response."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    gold_set_id = uuid4()
    revision_id = uuid4()
    entry_id = uuid4()
    expected_chunk = uuid4()

    reader = _FakeGoldSetReader()
    reader.get_returns = GoldSetWithCurrentRevision(
        gold_set=GoldSet(
            id=gold_set_id, tenant_id=_TENANT_UUID_AS_UUID,
            jurisdiction="eu-west", name="baseline",
            created_by_user_id="alice", created_at=_NOW,
            current_revision_id=revision_id,
        ),
        current_revision=GoldSetRevision(
            id=revision_id, gold_set_id=gold_set_id, revision_number=1,
            status=GoldSetRevisionStatus.FINALIZED, created_by_user_id="alice",
            created_at=_NOW, finalized_at=_NOW,
            this_event_hash="a" * 64, previous_event_hash="0" * 64,
        ),
        entries=(
            GoldSetEntry(
                id=entry_id, gold_set_revision_id=revision_id, entry_index=0,
                query="lvt?", expected_chunk_ids=(expected_chunk,),
            ),
        ),
    )

    repo = _FakeEvaluationRunRepository()
    audit = _FakeAuditPort()
    runner = _FakeRetrievalRunnerPort()
    app = _build_app(
        gold_set_reader=reader,
        evaluation_run_repository=repo,
        audit_port=audit,
        retrieval_runner_port=runner,
    )
    client = TestClient(app)

    response = client.post(
        "/evaluation-runs",
        json={"gold_set_id": str(gold_set_id)},
        headers=_auth_headers(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["run"]["status"] == "completed"
    assert body["run"]["invoked_by_user_id"] == "alice"
    # Two strategies (vector_only, graph_only) × one entry = 2 result rows.
    assert len(body["results"]) == 2
    # Two strategies → 2 aggregate rows.
    assert len(body["aggregates"]) == 2
    # Audit chain anchored: run_start + 2 result_appends + 2 aggregate_appends + run_terminal = 6
    assert len(audit.events) == 6
    # Runner invoked per (entry, strategy) pair.
    assert len(runner.calls) == 2


def test_start_evaluation_run_400_when_gold_set_has_no_finalized_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    gold_set_id = uuid4()
    reader = _FakeGoldSetReader()
    reader.get_returns = GoldSetWithCurrentRevision(
        gold_set=GoldSet(
            id=gold_set_id, tenant_id=_TENANT_UUID_AS_UUID,
            jurisdiction="eu-west", name="baseline",
            created_by_user_id="alice", created_at=_NOW,
            current_revision_id=None,  # no finalized revision
        ),
        current_revision=None,
        entries=(),
    )
    app = _build_app(
        gold_set_reader=reader,
        evaluation_run_repository=_FakeEvaluationRunRepository(),
        audit_port=_FakeAuditPort(),
        retrieval_runner_port=_FakeRetrievalRunnerPort(),
    )
    client = TestClient(app)

    response = client.post(
        "/evaluation-runs",
        json={"gold_set_id": str(gold_set_id)},
        headers=_auth_headers(),
    )

    assert response.status_code == 400
    assert (
        response.json()["error_code"] == "gold_set_missing_finalized_revision"
    )


def test_start_evaluation_run_404_when_gold_set_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    reader = _FakeGoldSetReader()
    reader.get_returns = None
    app = _build_app(
        gold_set_reader=reader,
        evaluation_run_repository=_FakeEvaluationRunRepository(),
        audit_port=_FakeAuditPort(),
        retrieval_runner_port=_FakeRetrievalRunnerPort(),
    )
    client = TestClient(app)

    response = client.post(
        "/evaluation-runs",
        json={"gold_set_id": str(uuid4())},
        headers=_auth_headers(),
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "gold_set_not_found"


# ---------------------------------------------------------------------------
# GET /evaluation-runs and GET /evaluation-runs/{id}
# ---------------------------------------------------------------------------


def test_list_evaluation_runs_200(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    reader = _FakeEvaluationRunReader()
    run = EvaluationRun(
        id=uuid4(), tenant_id=_TENANT_UUID_AS_UUID, jurisdiction="eu-west",
        gold_set_id=uuid4(), gold_set_revision_id=uuid4(),
        invoked_by_user_id="alice", invoked_at=_NOW,
        completed_at=_NOW.replace(second=10),
        status=EvaluationRunStatus.COMPLETED,
    )
    reader.list_returns = EvaluationRunListPage(
        runs=(run,), next_cursor=None,
    )
    app = _build_app(evaluation_run_reader=reader)
    client = TestClient(app)

    response = client.get("/evaluation-runs", headers=_auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["status"] == "completed"


def test_get_evaluation_run_404_on_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    reader = _FakeEvaluationRunReader()
    reader.snapshot_returns = None
    app = _build_app(evaluation_run_reader=reader)
    client = TestClient(app)

    response = client.get(
        f"/evaluation-runs/{uuid4()}", headers=_auth_headers()
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "evaluation_run_not_found"


def test_get_evaluation_run_200_returns_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    reader = _FakeEvaluationRunReader()
    run_id = uuid4()
    run = EvaluationRun(
        id=run_id, tenant_id=_TENANT_UUID_AS_UUID, jurisdiction="eu-west",
        gold_set_id=uuid4(), gold_set_revision_id=uuid4(),
        invoked_by_user_id="alice", invoked_at=_NOW,
        completed_at=_NOW.replace(second=10),
        status=EvaluationRunStatus.COMPLETED,
    )
    aggregate = EvaluationAggregate(
        id=uuid4(), evaluation_run_id=run_id,
        retrieval_strategy="vector_only",
        recall_at_k_mean={1: 0.5, 3: 0.8, 5: 0.9, 10: 1.0},
        precision_at_k_mean={1: 0.5, 3: 0.27, 5: 0.18, 10: 0.1},
        mrr_mean=Decimal("0.66"),
        latency_ms_p50=45, latency_ms_p95=80, latency_ms_mean=55,
    )
    reader.snapshot_returns = EvaluationRunSnapshot(
        run=run, results=(), aggregates=(aggregate,),
    )
    app = _build_app(evaluation_run_reader=reader)
    client = TestClient(app)

    response = client.get(
        f"/evaluation-runs/{run_id}", headers=_auth_headers()
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run"]["id"] == str(run_id)
    assert len(body["aggregates"]) == 1
    assert body["aggregates"][0]["retrieval_strategy"] == "vector_only"
