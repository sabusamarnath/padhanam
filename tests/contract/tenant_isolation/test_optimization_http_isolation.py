"""HTTP-layer tenant-isolation scenarios for the optimization routes (D24, D112, S42).

Five scenarios extend the D24 harness with the optimization HTTP
surface. The privacy-preserving 404 policy from D103 (no security
event on cross-tenant 404, identical to the audit-event-not-found
case) applies across optimization routes per D112.

- **Scenario A.** Cross-tenant ``GET /optimization-runs/{id}``
  returns 404 ``optimization_run_not_found``.

- **Scenario B.** Cross-tenant ``GET /recommendations/{id}`` returns
  404 ``recommendation_not_found``.

- **Scenario C.** Cross-tenant ``GET /recommendations`` filtered list
  returns empty. List-no-results is structurally indistinguishable
  from no-results-on-tenant, no security event.

- **Scenario D.** Cross-tenant ``POST /recommendations/{id}/acknowledge``
  returns 404 ``recommendation_not_found`` — the
  ``acknowledge_recommendation`` use case's reader returns None for
  cross-tenant access and RecommendationNotFoundError fires.

- **Scenario E.** Unauthenticated request to either route tree returns
  401 from the auth middleware before any route handler runs.
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
from contexts.audit.domain.events import AuditEvent
from contexts.optimization.domain import (
    OptimizationRun,
    OptimizationRunStatus,
    Recommendation,
    RecommendationCategory,
    RecommendationStatus,
)
from contexts.optimization.domain.evidence_citation import (
    RetrievalStrategyEvidenceCitation,
    StrategyComparison,
)
from contexts.optimization.ports.optimization_run_reader import (
    OptimizationRunListPage,
    OptimizationRunSnapshot,
)
from contexts.optimization.ports.recommendation_reader import (
    RecommendationListPage,
)
from padhanam.events import SynchronousEventBus
from padhanam.security.auth import issue_dev_token
from shared_kernel import TenantContext


_TENANT_A = "00000000-0000-4000-8000-0000000000a1"
_TENANT_B = "00000000-0000-4000-8000-0000000000a2"
_TENANT_A_UUID = UUID(_TENANT_A)
_TENANT_B_UUID = UUID(_TENANT_B)
_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc)


def _tenant_a_context() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_A,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_A,
    )


def _token_for_tenant_a() -> str:
    return issue_dev_token(
        subject="alice", tenant_id=_TENANT_A, roles=["agent.invoke"]
    )


def _make_recommendation(*, tenant_id: UUID) -> Recommendation:
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
    return Recommendation(
        id=uuid4(),
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        category=RecommendationCategory.RETRIEVAL_STRATEGY,
        subject="x",
        text="x",
        evidence_citations=(citation,),
        status=RecommendationStatus.GENERATED,
        generated_at=_NOW,
        generated_by_run_id=uuid4(),
        last_transition_at=_NOW,
        last_transition_by_user_id=None,
    )


class _TenantScopedOptimizationRunReader:
    def __init__(self) -> None:
        self._runs: dict[tuple[str, UUID], OptimizationRunSnapshot] = {}

    def put(self, tenant_id: str, snapshot: OptimizationRunSnapshot) -> None:
        self._runs[(tenant_id, snapshot.run.id)] = snapshot

    async def get_optimization_run(self, *, tenant_context, run_id):
        key = (str(tenant_context.tenant_id), run_id)
        return self._runs.get(key)

    async def list_optimization_runs(
        self, *, tenant_context, cursor, page_size
    ):
        tid = str(tenant_context.tenant_id)
        visible = [s.run for (t, _), s in self._runs.items() if t == tid]
        return OptimizationRunListPage(
            runs=tuple(visible), next_cursor=None
        )


class _TenantScopedRecommendationReader:
    def __init__(self) -> None:
        self._recs: dict[tuple[str, UUID], Recommendation] = {}

    def put(self, tenant_id: str, rec: Recommendation) -> None:
        self._recs[(tenant_id, rec.id)] = rec

    async def get_recommendation(
        self, *, tenant_context, recommendation_id
    ):
        key = (str(tenant_context.tenant_id), recommendation_id)
        return self._recs.get(key)

    async def list_recommendations(
        self, *, tenant_context, filters, cursor, page_size
    ):
        tid = str(tenant_context.tenant_id)
        visible = [r for (t, _), r in self._recs.items() if t == tid]
        if filters.categories is not None:
            visible = [
                r for r in visible if r.category in filters.categories
            ]
        if filters.statuses is not None:
            visible = [r for r in visible if r.status in filters.statuses]
        return RecommendationListPage(
            recommendations=tuple(visible), next_cursor=None
        )


class _NoopRecommendationRepository:
    async def persist_recommendation(self, **_):
        pass

    async def persist_status_transition(self, **_):
        pass


class _NoopAuditPort:
    async def emit(self, event: AuditEvent) -> None:
        pass


def _build_app(
    *,
    optimization_run_reader=None,
    recommendation_reader=None,
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
            "apps.api.routers.optimization",
            fromlist=["optimization_run_router"],
        ).optimization_run_router
    )
    app.include_router(
        __import__(
            "apps.api.routers.optimization", fromlist=["recommendation_router"]
        ).recommendation_router
    )
    app.dependency_overrides[get_tenant_context] = lambda: _tenant_a_context()
    if optimization_run_reader is not None:
        app.dependency_overrides[get_optimization_run_reader] = (
            lambda: optimization_run_reader
        )
    if recommendation_reader is not None:
        app.dependency_overrides[get_recommendation_reader] = (
            lambda: recommendation_reader
        )
    app.dependency_overrides[get_recommendation_repository] = (
        lambda: _NoopRecommendationRepository()
    )
    app.dependency_overrides[get_audit_port] = lambda: _NoopAuditPort()
    from apps.api._errors import register_optimization_error_handlers
    register_optimization_error_handlers(app)
    return app


# ---------------------------------------------------------------------------
# Scenario A: cross-tenant GET /optimization-runs/{id} → 404
# ---------------------------------------------------------------------------


def test_scenario_a_cross_tenant_get_optimization_run_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-iso-a")
    reader = _TenantScopedOptimizationRunReader()
    run_id = uuid4()
    snapshot = OptimizationRunSnapshot(
        run=OptimizationRun(
            id=run_id, tenant_id=_TENANT_B_UUID, jurisdiction="eu-west",
            invoked_by_user_id="bob", invoked_at=_NOW,
            completed_at=_NOW.replace(second=5),
            status=OptimizationRunStatus.COMPLETED,
        )
    )
    reader.put(_TENANT_B, snapshot)
    app = _build_app(optimization_run_reader=reader)
    client = TestClient(app)

    response = client.get(
        f"/optimization-runs/{run_id}",
        headers={"Authorization": f"Bearer {_token_for_tenant_a()}"},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "optimization_run_not_found"
    assert body["correlation_id"]


# ---------------------------------------------------------------------------
# Scenario B: cross-tenant GET /recommendations/{id} → 404
# ---------------------------------------------------------------------------


def test_scenario_b_cross_tenant_get_recommendation_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-iso-b")
    reader = _TenantScopedRecommendationReader()
    recommendation = _make_recommendation(tenant_id=_TENANT_B_UUID)
    reader.put(_TENANT_B, recommendation)
    app = _build_app(recommendation_reader=reader)
    client = TestClient(app)

    response = client.get(
        f"/recommendations/{recommendation.id}",
        headers={"Authorization": f"Bearer {_token_for_tenant_a()}"},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "recommendation_not_found"
    assert body["correlation_id"]


# ---------------------------------------------------------------------------
# Scenario C: cross-tenant GET /recommendations → empty list
# ---------------------------------------------------------------------------


def test_scenario_c_cross_tenant_list_recommendations_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-iso-c")
    reader = _TenantScopedRecommendationReader()
    # Two recommendations on tenant_b, none on tenant_a.
    reader.put(_TENANT_B, _make_recommendation(tenant_id=_TENANT_B_UUID))
    reader.put(_TENANT_B, _make_recommendation(tenant_id=_TENANT_B_UUID))
    app = _build_app(recommendation_reader=reader)
    client = TestClient(app)

    response = client.get(
        "/recommendations?category=retrieval_strategy",
        headers={"Authorization": f"Bearer {_token_for_tenant_a()}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["next_cursor"] is None


# ---------------------------------------------------------------------------
# Scenario D: cross-tenant POST /recommendations/{id}/acknowledge → 404
# ---------------------------------------------------------------------------


def test_scenario_d_cross_tenant_acknowledge_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-iso-d")
    reader = _TenantScopedRecommendationReader()
    recommendation = _make_recommendation(tenant_id=_TENANT_B_UUID)
    reader.put(_TENANT_B, recommendation)
    app = _build_app(recommendation_reader=reader)
    client = TestClient(app)

    response = client.post(
        f"/recommendations/{recommendation.id}/acknowledge",
        headers={"Authorization": f"Bearer {_token_for_tenant_a()}"},
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "recommendation_not_found"


# ---------------------------------------------------------------------------
# Scenario E: unauthenticated → 401
# ---------------------------------------------------------------------------


def test_scenario_e_unauthenticated_request_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-iso-e")
    app = _build_app()
    client = TestClient(app)

    response_one = client.get("/optimization-runs")
    response_two = client.get(f"/optimization-runs/{uuid4()}")
    response_three = client.get("/recommendations")
    response_four = client.post(
        f"/recommendations/{uuid4()}/acknowledge",
    )

    assert response_one.status_code == 401
    assert response_two.status_code == 401
    assert response_three.status_code == 401
    assert response_four.status_code == 401
