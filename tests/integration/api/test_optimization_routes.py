"""Integration tests for the optimization HTTP routes (D112, S42).

Uses FastAPI TestClient with dependency_overrides per the established
pattern. Covers the synchronous engine kickoff (with empty evidence
exercising the substrate-gap skip path for model_choice and
prompt_revision), the read surface for runs and recommendations, the
lifecycle transitions (acknowledge / apply / reject) including the
409 ``recommendation_transition_not_permitted`` path, and the
discriminated-union citation surface on the recommendation responses.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.main import AppCompositions, create_app
from apps.api.routers.inference import get_tenant_context
from apps.api.routers.optimization import (
    get_audit_event_reader_for_evidence,
    get_audit_port,
    get_evaluation_run_reader_for_evidence,
    get_gold_set_reader_for_evidence,
    get_optimization_run_reader,
    get_optimization_run_repository,
    get_recommendation_reader,
    get_recommendation_repository,
    get_run_history_reader_for_evidence,
)
from contexts.audit.domain.events import AuditEvent
from contexts.optimization.domain import (
    OptimizationRun,
    OptimizationRunStatus,
    Recommendation,
    RecommendationCategory,
    RecommendationStatus,
    RecommendationStatusTransition,
)
from contexts.optimization.domain.evidence_citation import (
    RetrievalStrategyEvidenceCitation,
    StrategyComparison,
)
from contexts.optimization.domain.query_filters import (
    OptimizationRunListCursor,
    RecommendationListCursor,
    RecommendationListFilters,
)
from contexts.optimization.ports.optimization_run_reader import (
    OptimizationRunListPage,
    OptimizationRunSnapshot,
)
from contexts.optimization.ports.recommendation_reader import (
    RecommendationListPage,
)
from contexts.retrieval_evaluation.domain.query_filters import (
    EvaluationRunListCursor,
)
from contexts.retrieval_evaluation.ports.evaluation_run_reader import (
    EvaluationRunListPage,
)
from contexts.run_history.domain.query_filters import RunListCursor, RunListFilters
from contexts.run_history.ports.reader import RunListPage
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


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_token()}"}


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeOptimizationRunRepository:
    def __init__(self) -> None:
        self.runs: list[OptimizationRun] = []
        self.completed: list[dict[str, Any]] = []
        self.failed: list[UUID] = []

    async def persist_run(self, *, tenant_context, run):
        self.runs.append(run)

    async def mark_completed(
        self, *, tenant_context, run_id, completed_at, skipped_categories
    ):
        self.completed.append(
            {
                "run_id": run_id,
                "completed_at": completed_at,
                "skipped_categories": dict(skipped_categories),
            }
        )

    async def mark_failed(self, *, tenant_context, run_id, completed_at):
        self.failed.append(run_id)


class _FakeOptimizationRunReader:
    def __init__(self) -> None:
        self.get_returns: OptimizationRunSnapshot | None = None
        self.list_returns = OptimizationRunListPage(runs=(), next_cursor=None)

    async def get_optimization_run(self, *, tenant_context, run_id):
        return self.get_returns

    async def list_optimization_runs(
        self, *, tenant_context, cursor, page_size
    ):
        return self.list_returns


class _FakeRecommendationRepository:
    def __init__(self) -> None:
        self.persisted: list[Recommendation] = []
        self.transitions: list[
            tuple[Recommendation, RecommendationStatusTransition]
        ] = []

    async def persist_recommendation(self, *, tenant_context, recommendation):
        self.persisted.append(recommendation)

    async def persist_status_transition(
        self, *, tenant_context, updated_recommendation, transition
    ):
        self.transitions.append((updated_recommendation, transition))


class _FakeRecommendationReader:
    def __init__(self) -> None:
        self.get_returns: Recommendation | None = None
        self.list_returns = RecommendationListPage(
            recommendations=(), next_cursor=None
        )
        self.list_calls: list[
            tuple[
                TenantContext,
                RecommendationListFilters,
                RecommendationListCursor | None,
                int,
            ]
        ] = []

    async def get_recommendation(self, *, tenant_context, recommendation_id):
        return self.get_returns

    async def list_recommendations(
        self, *, tenant_context, filters, cursor, page_size
    ):
        self.list_calls.append((tenant_context, filters, cursor, page_size))
        return self.list_returns


class _FakeAuditPort:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def emit(self, event: AuditEvent) -> None:
        self.events.append(event)


class _FakeEvaluationRunReader:
    """Returns empty pages so retrieval_strategy_rule emits zero recs."""

    async def list_runs(self, *, tenant_context, cursor, page_size):
        return EvaluationRunListPage(runs=(), next_cursor=None)

    async def get_run_with_results_and_aggregates(
        self, *, tenant_context, run_id
    ):
        return None


class _FakeGoldSetReader:
    """Passive at S42 — retrieval_strategy_rule never invokes it directly."""

    async def list_gold_sets(self, *, tenant_context, cursor, page_size):
        from contexts.retrieval_evaluation.ports.reader import GoldSetListPage
        return GoldSetListPage(gold_sets=(), next_cursor=None)

    async def get_gold_set_with_current_revision(
        self, *, tenant_context, gold_set_id
    ):
        return None

    async def get_revision_with_entries(self, *, tenant_context, revision_id):
        return None

    async def find_current_draft_revision(self, *, tenant_context, gold_set_id):
        return None


class _FakeRunHistoryReader:
    """Returns empty pages so cost_optimization_rule emits zero recs."""

    async def get_run(self, *, tenant_context, run_id):
        return None

    async def list_runs_with_filters(
        self, *, tenant_context, filters: RunListFilters, cursor
    ):
        return RunListPage(runs=(), next_cursor=None)


class _FakeAuditEventReader:
    """Passive at S42 — no Phase 1 rule actively queries audit events."""

    async def get_event(self, *, destination, event_id, tenant_context):
        return None

    async def list_events(
        self, *, destination, tenant_context, filters, cursor, page_size
    ):
        raise NotImplementedError("not exercised by tests")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_recommendation(
    *, status: RecommendationStatus = RecommendationStatus.GENERATED,
) -> Recommendation:
    citation = RetrievalStrategyEvidenceCitation(
        evaluation_run_id=uuid4(),
        gold_set_id=uuid4(),
        comparison=StrategyComparison(
            strategy_a="vector_only",
            strategy_b="graph_only",
            recall_at_k_delta={1: 0.4, 3: 0.8, 5: 0.8, 10: 1.0},
            precision_at_k_delta={1: 0.4, 3: 0.27, 5: 0.18, 10: 0.1},
        ),
        caveats=(),
    )
    return Recommendation(
        id=uuid4(),
        tenant_id=_TENANT_UUID_AS_UUID,
        jurisdiction="eu-west",
        category=RecommendationCategory.RETRIEVAL_STRATEGY,
        subject="vector_only beats graph_only",
        text="recall@3 delta of 0.8 absolute",
        evidence_citations=(citation,),
        status=status,
        generated_at=_NOW,
        generated_by_run_id=uuid4(),
        last_transition_at=_NOW,
        last_transition_by_user_id=(
            None
            if status is RecommendationStatus.GENERATED
            else "earlier-actor"
        ),
    )


def _build_app(
    *,
    optimization_run_repository=None,
    optimization_run_reader=None,
    recommendation_repository=None,
    recommendation_reader=None,
    audit_port=None,
    evaluation_run_reader=None,
    gold_set_reader=None,
    run_history_reader=None,
    audit_event_reader=None,
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
            "apps.api.routers.optimization", fromlist=["optimization_run_router"]
        ).optimization_run_router
    )
    app.include_router(
        __import__(
            "apps.api.routers.optimization", fromlist=["recommendation_router"]
        ).recommendation_router
    )

    app.dependency_overrides[get_tenant_context] = (
        lambda: _tenant_context_fixture()
    )
    if optimization_run_repository is not None:
        app.dependency_overrides[get_optimization_run_repository] = (
            lambda: optimization_run_repository
        )
    if optimization_run_reader is not None:
        app.dependency_overrides[get_optimization_run_reader] = (
            lambda: optimization_run_reader
        )
    if recommendation_repository is not None:
        app.dependency_overrides[get_recommendation_repository] = (
            lambda: recommendation_repository
        )
    if recommendation_reader is not None:
        app.dependency_overrides[get_recommendation_reader] = (
            lambda: recommendation_reader
        )
    if audit_port is not None:
        app.dependency_overrides[get_audit_port] = lambda: audit_port
    if evaluation_run_reader is not None:
        app.dependency_overrides[get_evaluation_run_reader_for_evidence] = (
            lambda: evaluation_run_reader
        )
    if gold_set_reader is not None:
        app.dependency_overrides[get_gold_set_reader_for_evidence] = (
            lambda: gold_set_reader
        )
    if run_history_reader is not None:
        app.dependency_overrides[get_run_history_reader_for_evidence] = (
            lambda: run_history_reader
        )
    if audit_event_reader is not None:
        app.dependency_overrides[get_audit_event_reader_for_evidence] = (
            lambda: audit_event_reader
        )

    from apps.api._errors import register_optimization_error_handlers
    register_optimization_error_handlers(app)
    return app


# ---------------------------------------------------------------------------
# POST /optimization-runs
# ---------------------------------------------------------------------------


def test_start_optimization_run_synchronous_with_empty_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Synchronous kickoff returns completed run + zero recs + 2 skipped."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    run_repo = _FakeOptimizationRunRepository()
    rec_repo = _FakeRecommendationRepository()
    audit = _FakeAuditPort()
    app = _build_app(
        optimization_run_repository=run_repo,
        recommendation_repository=rec_repo,
        audit_port=audit,
        evaluation_run_reader=_FakeEvaluationRunReader(),
        gold_set_reader=_FakeGoldSetReader(),
        run_history_reader=_FakeRunHistoryReader(),
        audit_event_reader=_FakeAuditEventReader(),
    )
    client = TestClient(app)

    response = client.post("/optimization-runs", headers=_auth_headers())

    assert response.status_code == 201
    body = response.json()
    assert body["run"]["status"] == "completed"
    assert body["run"]["invoked_by_user_id"] == "alice"
    # Phase 1: model_choice and prompt_revision raise SubstrateGapError.
    assert set(body["run"]["skipped_categories"].keys()) == {
        "model_choice",
        "prompt_revision",
    }
    assert body["recommendations"] == []
    # Audit chain: run_start + run_terminal = 2 events (no recommendation
    # generations because all rules either emit zero or skip).
    assert len(audit.events) == 2


def test_start_optimization_run_threads_principal_to_invoked_by(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    run_repo = _FakeOptimizationRunRepository()
    rec_repo = _FakeRecommendationRepository()
    audit = _FakeAuditPort()
    app = _build_app(
        optimization_run_repository=run_repo,
        recommendation_repository=rec_repo,
        audit_port=audit,
        evaluation_run_reader=_FakeEvaluationRunReader(),
        gold_set_reader=_FakeGoldSetReader(),
        run_history_reader=_FakeRunHistoryReader(),
        audit_event_reader=_FakeAuditEventReader(),
    )
    client = TestClient(app)
    response = client.post("/optimization-runs", headers=_auth_headers())
    assert response.status_code == 201
    assert run_repo.runs[0].invoked_by_user_id == "alice"


# ---------------------------------------------------------------------------
# GET /optimization-runs and /optimization-runs/{id}
# ---------------------------------------------------------------------------


def test_list_optimization_runs_200(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    reader = _FakeOptimizationRunReader()
    run = OptimizationRun(
        id=uuid4(),
        tenant_id=_TENANT_UUID_AS_UUID,
        jurisdiction="eu-west",
        invoked_by_user_id="alice",
        invoked_at=_NOW,
        completed_at=_NOW.replace(second=5),
        status=OptimizationRunStatus.COMPLETED,
    )
    reader.list_returns = OptimizationRunListPage(
        runs=(run,), next_cursor=None
    )
    app = _build_app(optimization_run_reader=reader)
    client = TestClient(app)

    response = client.get("/optimization-runs", headers=_auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["status"] == "completed"


def test_get_optimization_run_404_on_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    reader = _FakeOptimizationRunReader()
    reader.get_returns = None
    app = _build_app(optimization_run_reader=reader)
    client = TestClient(app)
    response = client.get(
        f"/optimization-runs/{uuid4()}", headers=_auth_headers()
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "optimization_run_not_found"


def test_get_optimization_run_200_returns_aggregate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    reader = _FakeOptimizationRunReader()
    run_id = uuid4()
    run = OptimizationRun(
        id=run_id,
        tenant_id=_TENANT_UUID_AS_UUID,
        jurisdiction="eu-west",
        invoked_by_user_id="alice",
        invoked_at=_NOW,
        completed_at=_NOW.replace(second=5),
        status=OptimizationRunStatus.COMPLETED,
    )
    reader.get_returns = OptimizationRunSnapshot(run=run)
    app = _build_app(optimization_run_reader=reader)
    client = TestClient(app)

    response = client.get(
        f"/optimization-runs/{run_id}", headers=_auth_headers()
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(run_id)


# ---------------------------------------------------------------------------
# GET /recommendations and /recommendations/{id}
# ---------------------------------------------------------------------------


def test_list_recommendations_200_with_discriminated_citation_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recommendation list responses include the discriminated-union citation."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    reader = _FakeRecommendationReader()
    recommendation = _make_recommendation()
    reader.list_returns = RecommendationListPage(
        recommendations=(recommendation,), next_cursor=None,
    )
    app = _build_app(recommendation_reader=reader)
    client = TestClient(app)

    response = client.get("/recommendations", headers=_auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    citation = body["items"][0]["evidence_citations"][0]
    assert citation["category"] == "retrieval_strategy"
    assert citation["comparison"]["strategy_a"] == "vector_only"


def test_list_recommendations_threads_category_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    reader = _FakeRecommendationReader()
    app = _build_app(recommendation_reader=reader)
    client = TestClient(app)

    response = client.get(
        "/recommendations?category=retrieval_strategy&status=generated",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    tenant_context, filters, _, _ = reader.list_calls[0]
    assert tenant_context.tenant_id == _TENANT_UUID
    assert filters.categories == (RecommendationCategory.RETRIEVAL_STRATEGY,)
    assert filters.statuses == (RecommendationStatus.GENERATED,)


def test_list_recommendations_400_on_unknown_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    reader = _FakeRecommendationReader()
    app = _build_app(recommendation_reader=reader)
    client = TestClient(app)
    response = client.get(
        "/recommendations?category=nonsense", headers=_auth_headers()
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "invalid_optimization_filter"


def test_get_recommendation_404_on_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    reader = _FakeRecommendationReader()
    reader.get_returns = None
    app = _build_app(recommendation_reader=reader)
    client = TestClient(app)
    response = client.get(
        f"/recommendations/{uuid4()}", headers=_auth_headers()
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "recommendation_not_found"


def test_get_recommendation_200_with_caveat_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    reader = _FakeRecommendationReader()
    reader.get_returns = _make_recommendation()
    app = _build_app(recommendation_reader=reader)
    client = TestClient(app)
    response = client.get(
        f"/recommendations/{uuid4()}", headers=_auth_headers()
    )
    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "retrieval_strategy"
    assert body["evidence_citations"][0]["category"] == "retrieval_strategy"


# ---------------------------------------------------------------------------
# Lifecycle: acknowledge / apply / reject
# ---------------------------------------------------------------------------


def test_acknowledge_recommendation_200_threads_principal_subject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    reader = _FakeRecommendationReader()
    repo = _FakeRecommendationRepository()
    audit = _FakeAuditPort()
    recommendation = _make_recommendation()
    reader.get_returns = recommendation
    app = _build_app(
        recommendation_reader=reader,
        recommendation_repository=repo,
        audit_port=audit,
    )
    client = TestClient(app)

    response = client.post(
        f"/recommendations/{recommendation.id}/acknowledge",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommendation"]["status"] == "acknowledged"
    assert body["transition"]["to_status"] == "acknowledged"
    assert body["transition"]["transitioned_by_user_id"] == "alice"
    # The recommendation update + transition row are persisted together.
    updated, transition = repo.transitions[0]
    assert updated.status is RecommendationStatus.ACKNOWLEDGED
    assert transition.transitioned_by_user_id == "alice"
    # One audit event captures the lifecycle change.
    assert len(audit.events) == 1


def test_apply_recommendation_200_from_generated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    reader = _FakeRecommendationReader()
    repo = _FakeRecommendationRepository()
    audit = _FakeAuditPort()
    reader.get_returns = _make_recommendation()
    app = _build_app(
        recommendation_reader=reader,
        recommendation_repository=repo,
        audit_port=audit,
    )
    client = TestClient(app)
    response = client.post(
        f"/recommendations/{uuid4()}/apply", headers=_auth_headers()
    )
    assert response.status_code == 200
    assert response.json()["transition"]["to_status"] == "applied"


def test_reject_recommendation_200_from_acknowledged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    reader = _FakeRecommendationReader()
    repo = _FakeRecommendationRepository()
    audit = _FakeAuditPort()
    reader.get_returns = _make_recommendation(
        status=RecommendationStatus.ACKNOWLEDGED
    )
    app = _build_app(
        recommendation_reader=reader,
        recommendation_repository=repo,
        audit_port=audit,
    )
    client = TestClient(app)
    response = client.post(
        f"/recommendations/{uuid4()}/reject", headers=_auth_headers()
    )
    assert response.status_code == 200
    assert response.json()["transition"]["from_status"] == "acknowledged"
    assert response.json()["transition"]["to_status"] == "rejected"


def test_acknowledge_404_when_recommendation_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    reader = _FakeRecommendationReader()
    repo = _FakeRecommendationRepository()
    audit = _FakeAuditPort()
    reader.get_returns = None
    app = _build_app(
        recommendation_reader=reader,
        recommendation_repository=repo,
        audit_port=audit,
    )
    client = TestClient(app)
    response = client.post(
        f"/recommendations/{uuid4()}/acknowledge", headers=_auth_headers()
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "recommendation_not_found"


def test_apply_after_apply_returns_409_transition_not_permitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Terminal state (applied) cannot transition further."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test")
    reader = _FakeRecommendationReader()
    repo = _FakeRecommendationRepository()
    audit = _FakeAuditPort()
    reader.get_returns = _make_recommendation(
        status=RecommendationStatus.APPLIED
    )
    app = _build_app(
        recommendation_reader=reader,
        recommendation_repository=repo,
        audit_port=audit,
    )
    client = TestClient(app)
    response = client.post(
        f"/recommendations/{uuid4()}/apply", headers=_auth_headers()
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error_code"] == "recommendation_transition_not_permitted"
    assert body["details"]["from_status"] == "applied"
    assert body["details"]["to_status"] == "applied"
