"""HTTP-layer tenant-isolation scenarios for the retrieval-evaluation routes (D24, D112, S42).

Six scenarios extend the D24 harness with the retrieval-evaluation
HTTP surface:

- **Scenario A.** Cross-tenant ``GET /gold-sets/{id}`` with a
  tenant-A principal asking for a gold-set that lives only on
  tenant_b returns 404 ``gold_set_not_found``. No security event fires
  per the privacy-preserving structural-honesty argument from D103:
  per-tenant adapter scoping makes cross-tenant invisibility
  indistinguishable from genuine not-found at the single-resource
  altitude.

- **Scenario B.** Cross-tenant ``GET /gold-sets`` returns an empty
  list. List-no-results is structurally indistinguishable from
  no-results-on-this-tenant, so no security event fires.

- **Scenario C.** Cross-tenant ``POST /gold-sets/{id}/entries``
  attempting to append to a gold-set that lives only on tenant_b
  returns 404 ``gold_set_not_found``. The append use case's
  reader.find_current_draft_revision returns None, then
  get_gold_set_with_current_revision returns None, and
  GoldSetNotFoundError fires.

- **Scenario D.** Cross-tenant ``GET /evaluation-runs/{id}`` returns
  404 ``evaluation_run_not_found``. Same per-tenant-adapter argument
  as scenario A.

- **Scenario E.** Cross-tenant ``POST /evaluation-runs`` against a
  gold-set on another tenant returns 404 ``gold_set_not_found`` —
  the runner's reader sees None and the application-layer
  GoldSetNotFoundError fires.

- **Scenario F.** Unauthenticated ``GET /gold-sets`` returns 401 from
  the auth middleware before any route handler runs. The reader is
  never invoked. No route-level security event fires.

The harness uses FastAPI's TestClient with dependency_overrides per
scenario. The fake adapters key storage by (tenant_id, resource_id)
so cross-tenant access naturally surfaces None.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
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
    get_retrieval_runner_port,
)
from contexts.audit.domain.events import AuditEvent
from contexts.retrieval_evaluation.domain import (
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


class _TenantScopedGoldSetReader:
    """Stores gold-sets keyed by (tenant_id, gold_set_id).

    Per-tenant scoping: cross-tenant reads see None. Used in scenarios
    A, B, C, E to model the bound-tenant adapter.
    """

    def __init__(self) -> None:
        self._snapshots: dict[
            tuple[str, UUID], GoldSetWithCurrentRevision
        ] = {}

    def put(
        self, tenant_id: str, snapshot: GoldSetWithCurrentRevision
    ) -> None:
        self._snapshots[(tenant_id, snapshot.gold_set.id)] = snapshot

    async def list_gold_sets(
        self, *, tenant_context, cursor, page_size
    ) -> GoldSetListPage:
        tid = str(tenant_context.tenant_id)
        visible = [
            s.gold_set for (t, _), s in self._snapshots.items() if t == tid
        ]
        return GoldSetListPage(gold_sets=tuple(visible), next_cursor=None)

    async def get_gold_set_with_current_revision(
        self, *, tenant_context, gold_set_id: UUID
    ):
        key = (str(tenant_context.tenant_id), gold_set_id)
        return self._snapshots.get(key)

    async def get_revision_with_entries(
        self, *, tenant_context, revision_id: UUID
    ):
        return None

    async def find_current_draft_revision(
        self, *, tenant_context, gold_set_id: UUID
    ):
        return None


class _TenantScopedEvaluationRunReader:
    def __init__(self) -> None:
        self._snapshots: dict[tuple[str, UUID], EvaluationRunSnapshot] = {}

    def put(self, tenant_id: str, snapshot: EvaluationRunSnapshot) -> None:
        self._snapshots[(tenant_id, snapshot.run.id)] = snapshot

    async def list_runs(self, *, tenant_context, cursor, page_size):
        tid = str(tenant_context.tenant_id)
        visible = [
            s.run for (t, _), s in self._snapshots.items() if t == tid
        ]
        return EvaluationRunListPage(runs=tuple(visible), next_cursor=None)

    async def get_run_with_results_and_aggregates(
        self, *, tenant_context, run_id: UUID
    ):
        key = (str(tenant_context.tenant_id), run_id)
        return self._snapshots.get(key)


class _NoopRepository:
    """Catches calls that should not fire under tenant-isolation 404 paths."""

    def __init__(self) -> None:
        self.called = False

    async def persist_new_gold_set(self, **_):
        self.called = True

    async def open_new_draft_revision(self, **_):
        self.called = True

    async def append_entry(self, **_):
        self.called = True

    async def finalize_revision(self, **_):
        self.called = True

    async def persist_run(self, **_):
        self.called = True

    async def persist_result(self, **_):
        self.called = True

    async def persist_aggregate(self, **_):
        self.called = True

    async def mark_completed(self, **_):
        self.called = True

    async def mark_failed(self, **_):
        self.called = True


class _NoopAuditPort:
    async def emit(self, event: AuditEvent) -> None:
        pass


class _NoopRunnerPort:
    async def __call__(
        self, *, query, tenant_context, strategy_dispatch, top_k
    ):
        return RankedChunks(chunk_ids=(), latency_ms=5)


def _build_app(
    *,
    gold_set_reader,
    evaluation_run_reader=None,
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
    app.dependency_overrides[get_tenant_context] = lambda: _tenant_a_context()
    app.dependency_overrides[get_gold_set_reader] = lambda: gold_set_reader
    app.dependency_overrides[get_gold_set_repository] = lambda: _NoopRepository()
    app.dependency_overrides[get_evaluation_run_repository] = (
        lambda: _NoopRepository()
    )
    app.dependency_overrides[get_audit_port] = lambda: _NoopAuditPort()
    app.dependency_overrides[get_retrieval_runner_port] = (
        lambda: _NoopRunnerPort()
    )
    if evaluation_run_reader is not None:
        app.dependency_overrides[get_evaluation_run_reader] = (
            lambda: evaluation_run_reader
        )
    from apps.api._errors import register_retrieval_evaluation_error_handlers
    register_retrieval_evaluation_error_handlers(app)
    return app


def _make_gold_set_snapshot(
    *, tenant_id: UUID
) -> GoldSetWithCurrentRevision:
    gold_set_id = uuid4()
    revision_id = uuid4()
    revision = GoldSetRevision(
        id=revision_id, gold_set_id=gold_set_id, revision_number=1,
        status=GoldSetRevisionStatus.FINALIZED,
        created_by_user_id="alice", created_at=_NOW, finalized_at=_NOW,
        this_event_hash="a" * 64, previous_event_hash="0" * 64,
    )
    entry = GoldSetEntry(
        id=uuid4(), gold_set_revision_id=revision_id, entry_index=0,
        query="q", expected_chunk_ids=(uuid4(),),
    )
    return GoldSetWithCurrentRevision(
        gold_set=GoldSet(
            id=gold_set_id, tenant_id=tenant_id, jurisdiction="eu-west",
            name="other-tenant-set", created_by_user_id="bob",
            created_at=_NOW, current_revision_id=revision_id,
        ),
        current_revision=revision,
        entries=(entry,),
    )


# ---------------------------------------------------------------------------
# Scenario A: cross-tenant GET /gold-sets/{id} → 404
# ---------------------------------------------------------------------------


def test_scenario_a_cross_tenant_get_gold_set_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-iso-a")
    reader = _TenantScopedGoldSetReader()
    tenant_b_snapshot = _make_gold_set_snapshot(tenant_id=_TENANT_B_UUID)
    reader.put(_TENANT_B, tenant_b_snapshot)
    app = _build_app(gold_set_reader=reader)
    client = TestClient(app)

    response = client.get(
        f"/gold-sets/{tenant_b_snapshot.gold_set.id}",
        headers={"Authorization": f"Bearer {_token_for_tenant_a()}"},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "gold_set_not_found"
    # Privacy: error message must not leak the existence of the
    # gold-set on a different tenant; the generic "not found" wording
    # is what reaches the wire.
    assert "tenant_b" not in body["message"].lower()
    assert body["correlation_id"]


# ---------------------------------------------------------------------------
# Scenario B: cross-tenant GET /gold-sets → empty
# ---------------------------------------------------------------------------


def test_scenario_b_cross_tenant_list_gold_sets_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-iso-b")
    reader = _TenantScopedGoldSetReader()
    # Two gold-sets on tenant_b, none on tenant_a.
    reader.put(_TENANT_B, _make_gold_set_snapshot(tenant_id=_TENANT_B_UUID))
    reader.put(_TENANT_B, _make_gold_set_snapshot(tenant_id=_TENANT_B_UUID))
    app = _build_app(gold_set_reader=reader)
    client = TestClient(app)

    response = client.get(
        "/gold-sets",
        headers={"Authorization": f"Bearer {_token_for_tenant_a()}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["next_cursor"] is None


# ---------------------------------------------------------------------------
# Scenario C: cross-tenant POST /gold-sets/{id}/entries → 404
# ---------------------------------------------------------------------------


def test_scenario_c_cross_tenant_append_entry_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-iso-c")
    reader = _TenantScopedGoldSetReader()
    tenant_b_snapshot = _make_gold_set_snapshot(tenant_id=_TENANT_B_UUID)
    reader.put(_TENANT_B, tenant_b_snapshot)
    app = _build_app(gold_set_reader=reader)
    client = TestClient(app)

    response = client.post(
        f"/gold-sets/{tenant_b_snapshot.gold_set.id}/entries",
        json={"query": "x", "expected_chunk_ids": [str(uuid4())]},
        headers={"Authorization": f"Bearer {_token_for_tenant_a()}"},
    )

    # find_current_draft_revision returns None (no tenant_a draft);
    # get_gold_set_with_current_revision returns None (cross-tenant);
    # GoldSetNotFoundError fires → 404.
    assert response.status_code == 404
    assert response.json()["error_code"] == "gold_set_not_found"


# ---------------------------------------------------------------------------
# Scenario D: cross-tenant GET /evaluation-runs/{id} → 404
# ---------------------------------------------------------------------------


def test_scenario_d_cross_tenant_get_evaluation_run_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-iso-d")
    gold_set_reader = _TenantScopedGoldSetReader()
    run_reader = _TenantScopedEvaluationRunReader()
    run_id = uuid4()
    snapshot = EvaluationRunSnapshot(
        run=EvaluationRun(
            id=run_id, tenant_id=_TENANT_B_UUID, jurisdiction="eu-west",
            gold_set_id=uuid4(), gold_set_revision_id=uuid4(),
            invoked_by_user_id="bob", invoked_at=_NOW,
            completed_at=_NOW.replace(second=5),
            status=EvaluationRunStatus.COMPLETED,
        ),
        results=(),
        aggregates=(),
    )
    run_reader.put(_TENANT_B, snapshot)
    app = _build_app(
        gold_set_reader=gold_set_reader, evaluation_run_reader=run_reader
    )
    client = TestClient(app)

    response = client.get(
        f"/evaluation-runs/{run_id}",
        headers={"Authorization": f"Bearer {_token_for_tenant_a()}"},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "evaluation_run_not_found"
    assert body["correlation_id"]


# ---------------------------------------------------------------------------
# Scenario E: cross-tenant POST /evaluation-runs against cross-tenant gold-set → 404
# ---------------------------------------------------------------------------


def test_scenario_e_cross_tenant_start_evaluation_run_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-iso-e")
    gold_set_reader = _TenantScopedGoldSetReader()
    tenant_b_snapshot = _make_gold_set_snapshot(tenant_id=_TENANT_B_UUID)
    gold_set_reader.put(_TENANT_B, tenant_b_snapshot)
    app = _build_app(
        gold_set_reader=gold_set_reader,
        evaluation_run_reader=_TenantScopedEvaluationRunReader(),
    )
    client = TestClient(app)

    response = client.post(
        "/evaluation-runs",
        json={"gold_set_id": str(tenant_b_snapshot.gold_set.id)},
        headers={"Authorization": f"Bearer {_token_for_tenant_a()}"},
    )

    # Reader sees None for tenant_a; GoldSetNotFoundError fires.
    assert response.status_code == 404
    assert response.json()["error_code"] == "gold_set_not_found"


# ---------------------------------------------------------------------------
# Scenario F: unauthenticated GET /gold-sets → 401
# ---------------------------------------------------------------------------


def test_scenario_f_unauthenticated_request_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-iso-f")
    reader = _TenantScopedGoldSetReader()
    app = _build_app(gold_set_reader=reader)
    client = TestClient(app)

    response_one = client.get("/gold-sets")
    response_two = client.get(f"/gold-sets/{uuid4()}")
    response_three = client.get("/evaluation-runs")

    assert response_one.status_code == 401
    assert response_two.status_code == 401
    assert response_three.status_code == 401
