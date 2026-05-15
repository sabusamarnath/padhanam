"""Cursor pagination contract scenarios for the S42 HTTP surface (D112).

Verifies the consumer-visible cursor behaviour for the four new list
endpoints (GET /gold-sets, GET /evaluation-runs, GET /optimization-runs,
GET /recommendations):

- **Cursor round-trip.** A cursor returned in one page is opaque to
  the client and round-trips back to the server intact: passing it
  as the ``cursor=`` query parameter on the next request returns the
  next page. The cursor's internal shape (base64-encoded JSON keyed
  on (timestamp, id, page_size)) is implementation detail; the
  contract surface is that the server reproduces the same domain
  cursor value from the encoded string.

- **Limit enforcement.** ``page_size`` outside [1, PAGE_SIZE_CEILING]
  is rejected with 422 by FastAPI's query validation before the use
  case runs. PAGE_SIZE_CEILING is 50 across both contexts per the
  domain layer; D112's commitment-4 framing of 200 was forward-
  affordance not Phase 1 reality.

- **Malformed cursor.** A non-base64 cursor or a base64 cursor that
  does not decode to the expected JSON schema raises
  ``MalformedCursorError`` at the use-case boundary; the registered
  handler translates to 400 ``malformed_<context>_cursor``.

Each context has its own cursor codec; the tests cover one round-trip
per cursor type plus the malformed-cursor 400 path per context.
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
    get_audit_port,
    get_optimization_run_reader,
    get_recommendation_reader,
    get_recommendation_repository,
)
from apps.api.routers.retrieval_evaluation import (
    get_evaluation_run_reader,
    get_gold_set_reader,
)
from contexts.audit.domain.events import AuditEvent
from contexts.optimization.application.cursors import (
    decode_optimization_run_cursor,
    decode_recommendation_cursor,
    encode_optimization_run_cursor,
    encode_recommendation_cursor,
)
from contexts.optimization.domain.query_filters import (
    OptimizationRunListCursor,
    RecommendationListCursor,
)
from contexts.optimization.ports.optimization_run_reader import (
    OptimizationRunListPage,
)
from contexts.optimization.ports.recommendation_reader import (
    RecommendationListPage,
)
from contexts.retrieval_evaluation.application.cursor import (
    decode as decode_gold_set_cursor,
    decode_run_cursor as decode_evaluation_run_cursor,
    encode as encode_gold_set_cursor,
    encode_run_cursor as encode_evaluation_run_cursor,
)
from contexts.retrieval_evaluation.domain.query_filters import (
    EvaluationRunListCursor,
    GoldSetListCursor,
)
from contexts.retrieval_evaluation.ports.evaluation_run_reader import (
    EvaluationRunListPage,
)
from contexts.retrieval_evaluation.ports.reader import GoldSetListPage
from padhanam.events import SynchronousEventBus
from padhanam.security.auth import issue_dev_token
from shared_kernel import TenantContext


_TENANT_A = "00000000-0000-4000-8000-0000000000a1"
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


# ---------------------------------------------------------------------------
# Capturing fake readers that record the cursor they receive
# ---------------------------------------------------------------------------


class _CursorCapturingGoldSetReader:
    def __init__(self) -> None:
        self.received_cursor: GoldSetListCursor | None = None

    async def list_gold_sets(
        self, *, tenant_context, cursor, page_size
    ) -> GoldSetListPage:
        self.received_cursor = cursor
        return GoldSetListPage(gold_sets=(), next_cursor=None)

    async def get_gold_set_with_current_revision(self, **_):
        return None

    async def get_revision_with_entries(self, **_):
        return None

    async def find_current_draft_revision(self, **_):
        return None


class _CursorCapturingEvaluationRunReader:
    def __init__(self) -> None:
        self.received_cursor: EvaluationRunListCursor | None = None

    async def list_runs(
        self, *, tenant_context, cursor, page_size
    ) -> EvaluationRunListPage:
        self.received_cursor = cursor
        return EvaluationRunListPage(runs=(), next_cursor=None)

    async def get_run_with_results_and_aggregates(self, **_):
        return None


class _CursorCapturingOptimizationRunReader:
    def __init__(self) -> None:
        self.received_cursor: OptimizationRunListCursor | None = None

    async def get_optimization_run(self, **_):
        return None

    async def list_optimization_runs(
        self, *, tenant_context, cursor, page_size
    ) -> OptimizationRunListPage:
        self.received_cursor = cursor
        return OptimizationRunListPage(runs=(), next_cursor=None)


class _CursorCapturingRecommendationReader:
    def __init__(self) -> None:
        self.received_cursor: RecommendationListCursor | None = None
        self.received_filters = None

    async def get_recommendation(self, **_):
        return None

    async def list_recommendations(
        self, *, tenant_context, filters, cursor, page_size
    ) -> RecommendationListPage:
        self.received_cursor = cursor
        self.received_filters = filters
        return RecommendationListPage(recommendations=(), next_cursor=None)


def _build_app() -> Any:
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
            fromlist=["optimization_run_router"],
        ).optimization_run_router
    )
    app.include_router(
        __import__(
            "apps.api.routers.optimization",
            fromlist=["recommendation_router"],
        ).recommendation_router
    )
    app.dependency_overrides[get_tenant_context] = lambda: _tenant_a_context()

    class _NoopAuditPort:
        async def emit(self, event: AuditEvent) -> None:
            pass

    class _NoopRecommendationRepository:
        async def persist_recommendation(self, **_):
            pass

        async def persist_status_transition(self, **_):
            pass

    app.dependency_overrides[get_audit_port] = lambda: _NoopAuditPort()
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


# ---------------------------------------------------------------------------
# Gold-set cursor
# ---------------------------------------------------------------------------


def test_gold_set_cursor_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Encoded cursor passes through HTTP and decodes to the same domain cursor."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-pagination")
    reader = _CursorCapturingGoldSetReader()
    app = _build_app()
    app.dependency_overrides[get_gold_set_reader] = lambda: reader
    client = TestClient(app)

    original_cursor = GoldSetListCursor(
        created_at=_NOW, id=uuid4(), page_size=25
    )
    encoded = encode_gold_set_cursor(original_cursor)
    response = client.get(
        "/gold-sets",
        params={"cursor": encoded, "page_size": 25},
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    assert reader.received_cursor == original_cursor
    # Sanity: the codec's decode of the same encoded string also
    # returns the original domain cursor.
    assert decode_gold_set_cursor(encoded) == original_cursor


def test_gold_set_malformed_cursor_returns_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-pagination")
    reader = _CursorCapturingGoldSetReader()
    app = _build_app()
    app.dependency_overrides[get_gold_set_reader] = lambda: reader
    client = TestClient(app)

    response = client.get(
        "/gold-sets",
        params={"cursor": "not-valid-base64$$$"},
        headers=_auth_headers(),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "malformed_retrieval_evaluation_cursor"
    assert body["correlation_id"]


def test_gold_set_page_size_above_ceiling_returns_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-pagination")
    app = _build_app()
    app.dependency_overrides[get_gold_set_reader] = (
        lambda: _CursorCapturingGoldSetReader()
    )
    client = TestClient(app)

    response = client.get(
        "/gold-sets", params={"page_size": 999}, headers=_auth_headers()
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Evaluation-run cursor
# ---------------------------------------------------------------------------


def test_evaluation_run_cursor_round_trip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-pagination")
    reader = _CursorCapturingEvaluationRunReader()
    app = _build_app()
    app.dependency_overrides[get_evaluation_run_reader] = lambda: reader
    client = TestClient(app)

    original_cursor = EvaluationRunListCursor(
        invoked_at=_NOW, id=uuid4(), page_size=15
    )
    encoded = encode_evaluation_run_cursor(original_cursor)
    response = client.get(
        "/evaluation-runs",
        params={"cursor": encoded, "page_size": 15},
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    assert reader.received_cursor == original_cursor
    assert decode_evaluation_run_cursor(encoded) == original_cursor


def test_evaluation_run_malformed_cursor_returns_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-pagination")
    app = _build_app()
    app.dependency_overrides[get_evaluation_run_reader] = (
        lambda: _CursorCapturingEvaluationRunReader()
    )
    client = TestClient(app)

    response = client.get(
        "/evaluation-runs", params={"cursor": "@@@"},
        headers=_auth_headers(),
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == (
        "malformed_retrieval_evaluation_cursor"
    )


# ---------------------------------------------------------------------------
# Optimization-run cursor
# ---------------------------------------------------------------------------


def test_optimization_run_cursor_round_trip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-pagination")
    reader = _CursorCapturingOptimizationRunReader()
    app = _build_app()
    app.dependency_overrides[get_optimization_run_reader] = lambda: reader
    client = TestClient(app)

    original_cursor = OptimizationRunListCursor(
        invoked_at=_NOW, id=uuid4(), page_size=15
    )
    encoded = encode_optimization_run_cursor(original_cursor)
    response = client.get(
        "/optimization-runs",
        params={"cursor": encoded, "page_size": 15},
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    assert reader.received_cursor == original_cursor
    assert decode_optimization_run_cursor(encoded) == original_cursor


def test_optimization_run_malformed_cursor_returns_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-pagination")
    app = _build_app()
    app.dependency_overrides[get_optimization_run_reader] = (
        lambda: _CursorCapturingOptimizationRunReader()
    )
    client = TestClient(app)

    response = client.get(
        "/optimization-runs", params={"cursor": "###"},
        headers=_auth_headers(),
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "malformed_optimization_cursor"


# ---------------------------------------------------------------------------
# Recommendation cursor
# ---------------------------------------------------------------------------


def test_recommendation_cursor_round_trip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-pagination")
    reader = _CursorCapturingRecommendationReader()
    app = _build_app()
    app.dependency_overrides[get_recommendation_reader] = lambda: reader
    client = TestClient(app)

    original_cursor = RecommendationListCursor(
        generated_at=_NOW, id=uuid4(), page_size=10
    )
    encoded = encode_recommendation_cursor(original_cursor)
    response = client.get(
        "/recommendations",
        params={"cursor": encoded, "page_size": 10},
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    assert reader.received_cursor == original_cursor
    assert decode_recommendation_cursor(encoded) == original_cursor


def test_recommendation_malformed_cursor_returns_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-pagination")
    app = _build_app()
    app.dependency_overrides[get_recommendation_reader] = (
        lambda: _CursorCapturingRecommendationReader()
    )
    client = TestClient(app)

    response = client.get(
        "/recommendations", params={"cursor": "{{{"},
        headers=_auth_headers(),
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "malformed_optimization_cursor"
