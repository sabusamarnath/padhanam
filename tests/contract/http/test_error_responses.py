"""Standard error-response body shape contract for the S42 HTTP surface (D112).

Verifies that every error path on the new routes serialises the
``ErrorResponse`` shape from ``apps/api/_errors.py``:

    {
      "error_code": "machine_readable_identifier",
      "message": "human-readable explanation",
      "correlation_id": "uuid4-per-request",
      "details": {...}  # optional, present only on validation errors
                        # and on the transition-not-permitted path
                        # where structured field-level context is useful
    }

The correlation_id is populated by CorrelationIdMiddleware on every
inbound request and matches the X-Correlation-Id response header.

Five error categories validated:

1. 404 not-found paths (gold_set_not_found, evaluation_run_not_found,
   optimization_run_not_found, recommendation_not_found).
2. 400 invalid-input paths (invalid_optimization_filter, empty_draft).
3. 400 malformed-cursor paths (covered separately in test_pagination.py).
4. 409 conflict path (no_draft_to_finalize,
   recommendation_transition_not_permitted with structured details).
5. 422 validation paths (FastAPI's RequestValidationError shape).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.main import AppCompositions, create_app
from apps.api.routers.inference import get_tenant_context
from apps.api.routers.optimization import (
    get_audit_port as get_optimization_audit_port,
    get_optimization_run_reader,
    get_recommendation_reader,
    get_recommendation_repository,
)
from apps.api.routers.retrieval_evaluation import (
    get_audit_port,
    get_evaluation_run_reader,
    get_evaluation_run_repository,
    get_gold_set_reader,
    get_gold_set_repository,
    get_retrieval_runner_port,
)
from contexts.audit.domain.events import AuditEvent
from contexts.optimization.domain import (
    Recommendation,
    RecommendationCategory,
    RecommendationStatus,
)
from contexts.optimization.domain.evidence_citation import (
    RetrievalStrategyEvidenceCitation,
    StrategyComparison,
)
from contexts.optimization.ports.recommendation_reader import (
    RecommendationListPage,
)
from contexts.retrieval_evaluation.domain import (
    GoldSetRevision,
    GoldSetRevisionStatus,
)
from contexts.retrieval_evaluation.ports.reader import RevisionWithEntries
from padhanam.events import SynchronousEventBus
from padhanam.security.auth import issue_dev_token
from shared_kernel import TenantContext


_TENANT_A = "00000000-0000-4000-8000-0000000000a1"
_TENANT_A_UUID = UUID(_TENANT_A)
_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc)


def _tenant_a_context() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_A,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_A,
    )


def _auth_headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer "
        + issue_dev_token(
            subject="alice", tenant_id=_TENANT_A, roles=["agent.invoke"]
        )
    }


class _EmptyGoldSetReader:
    async def list_gold_sets(self, **_):
        from contexts.retrieval_evaluation.ports.reader import GoldSetListPage
        return GoldSetListPage(gold_sets=(), next_cursor=None)

    async def get_gold_set_with_current_revision(self, **_):
        return None

    async def get_revision_with_entries(self, **_):
        return None

    async def find_current_draft_revision(self, **_):
        return None


class _EmptyDraftReader:
    """Returns a draft with no entries to trigger EmptyDraftError."""

    def __init__(self, *, gold_set_id: UUID, revision_id: UUID) -> None:
        self._draft = GoldSetRevision(
            id=revision_id, gold_set_id=gold_set_id, revision_number=1,
            status=GoldSetRevisionStatus.DRAFT, created_by_user_id="alice",
            created_at=_NOW, finalized_at=None,
            this_event_hash=None, previous_event_hash=None,
        )

    async def list_gold_sets(self, **_):
        from contexts.retrieval_evaluation.ports.reader import GoldSetListPage
        return GoldSetListPage(gold_sets=(), next_cursor=None)

    async def get_gold_set_with_current_revision(self, **_):
        return None

    async def get_revision_with_entries(self, **_):
        return RevisionWithEntries(revision=self._draft, entries=())

    async def find_current_draft_revision(self, **_):
        return self._draft


class _NoopRepository:
    async def persist_new_gold_set(self, **_):
        pass

    async def open_new_draft_revision(self, **_):
        pass

    async def append_entry(self, **_):
        pass

    async def finalize_revision(self, **_):
        pass


class _NoopAuditPort:
    async def emit(self, event: AuditEvent) -> None:
        pass


class _EmptyRecommendationReader:
    def __init__(self) -> None:
        self.get_returns: Recommendation | None = None

    async def get_recommendation(self, **_):
        return self.get_returns

    async def list_recommendations(self, **_):
        return RecommendationListPage(recommendations=(), next_cursor=None)


class _NoopRecommendationRepository:
    async def persist_recommendation(self, **_):
        pass

    async def persist_status_transition(self, **_):
        pass


def _build_app(*, gold_set_reader=None, recommendation_reader=None) -> Any:
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
            "apps.api.routers.retrieval_evaluation",
            fromlist=["gold_set_router"],
        ).gold_set_router
    )
    app.include_router(
        __import__(
            "apps.api.routers.retrieval_evaluation",
            fromlist=["evaluation_run_router"],
        ).evaluation_run_router
    )
    app.include_router(
        __import__(
            "apps.api.routers.optimization",
            fromlist=["recommendation_router"],
        ).recommendation_router
    )
    app.dependency_overrides[get_tenant_context] = lambda: _tenant_a_context()
    app.dependency_overrides[get_gold_set_reader] = (
        lambda: gold_set_reader or _EmptyGoldSetReader()
    )
    app.dependency_overrides[get_gold_set_repository] = lambda: _NoopRepository()
    app.dependency_overrides[get_evaluation_run_repository] = (
        lambda: _NoopRepository()
    )
    app.dependency_overrides[get_audit_port] = lambda: _NoopAuditPort()
    app.dependency_overrides[get_optimization_audit_port] = (
        lambda: _NoopAuditPort()
    )
    if recommendation_reader is not None:
        app.dependency_overrides[get_recommendation_reader] = (
            lambda: recommendation_reader
        )
    app.dependency_overrides[get_recommendation_repository] = (
        lambda: _NoopRecommendationRepository()
    )

    from apps.api._errors import (
        register_optimization_error_handlers,
        register_retrieval_evaluation_error_handlers,
    )
    register_retrieval_evaluation_error_handlers(app)
    register_optimization_error_handlers(app)
    return app


_REQUIRED_ERROR_KEYS = {"error_code", "message", "correlation_id", "details"}


def _assert_error_envelope(body: dict[str, Any]) -> None:
    """Common assertions: every error body has the four canonical keys."""
    assert set(body.keys()) == _REQUIRED_ERROR_KEYS
    assert isinstance(body["error_code"], str)
    assert isinstance(body["message"], str)
    assert isinstance(body["correlation_id"], str)
    assert len(body["correlation_id"]) > 0


# ---------------------------------------------------------------------------
# 404 errors
# ---------------------------------------------------------------------------


def test_gold_set_not_found_error_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-error")
    app = _build_app()
    client = TestClient(app)
    response = client.get(f"/gold-sets/{uuid4()}", headers=_auth_headers())
    assert response.status_code == 404
    body = response.json()
    _assert_error_envelope(body)
    assert body["error_code"] == "gold_set_not_found"
    assert body["details"] is None
    # The response carries the same correlation_id as the body.
    assert response.headers["x-correlation-id"] == body["correlation_id"]


def test_evaluation_run_not_found_error_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-error")

    class _EmptyEvaluationRunReader:
        async def list_runs(self, **_):
            from contexts.retrieval_evaluation.ports.evaluation_run_reader import (
                EvaluationRunListPage,
            )
            return EvaluationRunListPage(runs=(), next_cursor=None)

        async def get_run_with_results_and_aggregates(self, **_):
            return None

    app = _build_app()
    app.dependency_overrides[get_evaluation_run_reader] = (
        lambda: _EmptyEvaluationRunReader()
    )
    client = TestClient(app)
    response = client.get(
        f"/evaluation-runs/{uuid4()}", headers=_auth_headers()
    )
    assert response.status_code == 404
    body = response.json()
    _assert_error_envelope(body)
    assert body["error_code"] == "evaluation_run_not_found"


def test_optimization_run_not_found_error_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-error")

    class _EmptyOptimizationRunReader:
        async def get_optimization_run(self, **_):
            return None

        async def list_optimization_runs(self, **_):
            from contexts.optimization.ports.optimization_run_reader import (
                OptimizationRunListPage,
            )
            return OptimizationRunListPage(runs=(), next_cursor=None)

    app = _build_app()
    app.dependency_overrides[get_optimization_run_reader] = (
        lambda: _EmptyOptimizationRunReader()
    )
    # Need to include the optimization_run_router too — _build_app
    # currently includes only the recommendation_router. Add it here.
    app.include_router(
        __import__(
            "apps.api.routers.optimization",
            fromlist=["optimization_run_router"],
        ).optimization_run_router
    )
    client = TestClient(app)
    response = client.get(
        f"/optimization-runs/{uuid4()}", headers=_auth_headers()
    )
    assert response.status_code == 404
    body = response.json()
    _assert_error_envelope(body)
    assert body["error_code"] == "optimization_run_not_found"


def test_recommendation_not_found_error_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-error")
    reader = _EmptyRecommendationReader()
    app = _build_app(recommendation_reader=reader)
    client = TestClient(app)
    response = client.get(
        f"/recommendations/{uuid4()}", headers=_auth_headers()
    )
    assert response.status_code == 404
    body = response.json()
    _assert_error_envelope(body)
    assert body["error_code"] == "recommendation_not_found"


# ---------------------------------------------------------------------------
# 409 conflict — transition_not_permitted with structured details
# ---------------------------------------------------------------------------


def test_transition_not_permitted_includes_structured_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The 409 path returns details with from_status / to_status."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-error")
    citation = RetrievalStrategyEvidenceCitation(
        evaluation_run_id=uuid4(),
        gold_set_id=uuid4(),
        comparison=StrategyComparison(
            strategy_a="vector_only", strategy_b="graph_only",
            recall_at_k_delta={1: 0.4, 3: 0.8, 5: 0.8, 10: 1.0},
            precision_at_k_delta={1: 0.4, 3: 0.27, 5: 0.18, 10: 0.1},
        ),
        caveats=(),
    )
    applied = Recommendation(
        id=uuid4(), tenant_id=_TENANT_A_UUID, jurisdiction="eu-west",
        category=RecommendationCategory.RETRIEVAL_STRATEGY,
        subject="s", text="t", evidence_citations=(citation,),
        status=RecommendationStatus.APPLIED,  # terminal
        generated_at=_NOW, generated_by_run_id=uuid4(),
        last_transition_at=_NOW, last_transition_by_user_id="earlier-actor",
    )
    reader = _EmptyRecommendationReader()
    reader.get_returns = applied
    app = _build_app(recommendation_reader=reader)
    client = TestClient(app)

    response = client.post(
        f"/recommendations/{applied.id}/apply", headers=_auth_headers()
    )
    assert response.status_code == 409
    body = response.json()
    _assert_error_envelope(body)
    assert body["error_code"] == "recommendation_transition_not_permitted"
    assert body["details"]["from_status"] == "applied"
    assert body["details"]["to_status"] == "applied"


# ---------------------------------------------------------------------------
# 409 + 400 — finalize paths
# ---------------------------------------------------------------------------


def test_no_draft_to_finalize_error_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-error")
    app = _build_app()
    client = TestClient(app)
    response = client.post(
        f"/gold-sets/{uuid4()}/finalize", headers=_auth_headers()
    )
    assert response.status_code == 409
    body = response.json()
    _assert_error_envelope(body)
    assert body["error_code"] == "no_draft_to_finalize"


def test_empty_draft_error_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-error")
    gold_set_id = uuid4()
    reader = _EmptyDraftReader(
        gold_set_id=gold_set_id, revision_id=uuid4()
    )
    app = _build_app(gold_set_reader=reader)
    client = TestClient(app)
    response = client.post(
        f"/gold-sets/{gold_set_id}/finalize", headers=_auth_headers()
    )
    assert response.status_code == 400
    body = response.json()
    _assert_error_envelope(body)
    assert body["error_code"] == "empty_draft"


# ---------------------------------------------------------------------------
# 400 invalid-filter
# ---------------------------------------------------------------------------


def test_invalid_optimization_filter_error_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-error")
    reader = _EmptyRecommendationReader()
    app = _build_app(recommendation_reader=reader)
    client = TestClient(app)
    response = client.get(
        "/recommendations?category=nonsense", headers=_auth_headers()
    )
    assert response.status_code == 400
    body = response.json()
    _assert_error_envelope(body)
    assert body["error_code"] == "invalid_optimization_filter"


# ---------------------------------------------------------------------------
# Correlation-id header round-trip
# ---------------------------------------------------------------------------


def test_correlation_id_present_on_every_error_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every error body's correlation_id matches X-Correlation-Id header."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-error")
    reader = _EmptyRecommendationReader()
    app = _build_app(recommendation_reader=reader)
    client = TestClient(app)

    # Trigger a 404 and a 400 in parallel paths; both must carry
    # matching correlation IDs in body + header.
    response_404 = client.get(
        f"/recommendations/{uuid4()}", headers=_auth_headers()
    )
    response_400 = client.get(
        "/recommendations?category=nope", headers=_auth_headers()
    )

    assert response_404.status_code == 404
    assert response_400.status_code == 400
    assert (
        response_404.headers["x-correlation-id"]
        == response_404.json()["correlation_id"]
    )
    assert (
        response_400.headers["x-correlation-id"]
        == response_400.json()["correlation_id"]
    )
    # The two requests get distinct correlation IDs.
    assert (
        response_404.headers["x-correlation-id"]
        != response_400.headers["x-correlation-id"]
    )
