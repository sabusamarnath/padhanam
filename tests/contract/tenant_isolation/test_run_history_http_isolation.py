"""HTTP-layer tenant-isolation scenarios for the run-history routes (D24, D98, S34).

Four scenarios (17 through 20 in the D24 harness, extending S33's
16-scenario count to 20):

- **Scenario 17.** Cross-tenant ``GET /runs/{id}`` with a tenant-A
  principal asking for a run that lives only on tenant_b returns 404
  and fires a ``TENANT_SCOPE_VIOLATION`` security event. The reader
  sees the request bound to tenant_a's session and returns None; the
  route's privacy-preserving 404 shape (indistinguishable from
  genuinely-missing) holds.

- **Scenario 18.** Cross-tenant ``GET /runs`` with a tenant-A
  principal and filters that would match tenant_b's runs returns an
  empty list with NO security event. List-no-results is structurally
  indistinguishable from no-results-by-filter, so firing on every
  empty list would produce noise; the as-built asymmetry between
  ``/runs/{id}`` (fires on 404 because the request is specific) and
  ``/runs`` (does not fire on empty because the filter is broad) is
  the policy commit per D98.

- **Scenario 19.** Missing principal (no auth header) returns 401.
  The auth middleware fires before any route handler; no security
  event from the run-history routes (the AUTH_FAILURE category fires
  from the middleware separately).

- **Scenario 20.** Principal whose tenant is not in the registry
  returns 404 (not 401). The reused ``get_tenant_context`` dependency
  at ``apps/api/routers/inference.py`` raises HTTPException 404 when
  ``registry.get_tenant()`` returns None; the run-history routes
  inherit the same behaviour per the brief-versus-built-state
  reconciliation finding at S34 session-open (Appendix D, structural-
  honesty surface 1). The D98 error map names the path as
  ``tenant_not_found`` 404; no security event from the run-history
  routes because the dependency fires before the handler.

The harness uses FastAPI's TestClient with dependency_overrides to
substitute the reader and tenant-context resolver. The
``get_tenant_context`` and ``get_run_history_reader`` substitution
shapes track scenarios 17-19; scenario 20 reverts the
``get_tenant_context`` override to exercise the real-registry path
through a stub-registry that returns None for the principal's
tenant_id.
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
from apps.api.routers.run_history import (
    get_run_history_reader,
    get_security_event_logger,
)
from contexts.run_history.domain.query_filters import (
    PAGE_SIZE_CEILING,
    RunListCursor,
    RunListFilters,
)
from contexts.run_history.domain.run_record import RunRecord
from contexts.run_history.ports.reader import RunListPage
from padhanam.events import SynchronousEventBus
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
)
from padhanam.security.auth import issue_dev_token
from shared_kernel import TenantContext


_TENANT_A = "00000000-0000-4000-8000-0000000000a1"
_TENANT_B = "00000000-0000-4000-8000-0000000000a2"
_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)


def _tenant_a_context() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_A,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_A,
    )


def _make_run_record_for_tenant(tenant_id: str, run_id: UUID) -> RunRecord:
    return RunRecord(
        id=run_id,
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        agent_template_id=uuid4(),
        agent_template_version=1,
        input_message="x",
        output_content="y",
        started_at=_NOW,
        completed_at=_NOW.replace(second=30),
        termination_reason="content",
        iteration_count=1,
        total_cost_usd=Decimal("0.001"),
        trace_id=None,
        audit_start_hash="a" * 64,
        audit_end_hash="b" * 64,
        created_at=_NOW.replace(second=30),
    )


class _TenantScopedFakeReader:
    """Returns runs only for the bound tenant_id; cross-tenant reads see None.

    Models the per-tenant database isolation: a run that exists on
    tenant_b is invisible to a reader configured for tenant_a. The
    fake's storage is keyed by (tenant_id, run_id).
    """

    def __init__(self) -> None:
        self._runs: dict[tuple[str, UUID], RunRecord] = {}
        self.get_run_calls: list[tuple[TenantContext, UUID]] = []
        self.list_calls: list[
            tuple[TenantContext, RunListFilters, RunListCursor | None]
        ] = []

    def put(self, tenant_id: str, record: RunRecord) -> None:
        self._runs[(tenant_id, record.id)] = record

    async def get_run(
        self, *, tenant_context: TenantContext, run_id: UUID
    ) -> RunRecord | None:
        self.get_run_calls.append((tenant_context, run_id))
        key = (str(tenant_context.tenant_id), run_id)
        return self._runs.get(key)

    async def list_runs_with_filters(
        self,
        *,
        tenant_context: TenantContext,
        filters: RunListFilters,
        cursor: RunListCursor | None,
    ) -> RunListPage:
        self.list_calls.append((tenant_context, filters, cursor))
        tid = str(tenant_context.tenant_id)
        # Filter by tenant_id THEN apply filters. Only records on the
        # bound tenant are visible; cross-tenant filter matches are
        # invisible.
        visible = [r for (t, _rid), r in self._runs.items() if t == tid]
        if filters.agent_template_ids is not None:
            visible = [
                r for r in visible if r.agent_template_id in filters.agent_template_ids
            ]
        return RunListPage(runs=tuple(visible), next_cursor=None)


class _FakeSecurityEventLogger:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def emit(self, event: SecurityEvent) -> None:
        self.events.append(event)


def _build_app_with_tenant_a_context(
    *,
    reader: _TenantScopedFakeReader,
    security_events: _FakeSecurityEventLogger,
) -> Any:
    """App fixture: tenant context overridden to tenant_a."""

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
    app.dependency_overrides[get_tenant_context] = lambda: _tenant_a_context()
    app.dependency_overrides[get_run_history_reader] = lambda: reader
    app.dependency_overrides[get_security_event_logger] = lambda: security_events
    app.state.security_events = security_events
    return app


def _token_for_tenant_a() -> str:
    return issue_dev_token(
        subject="alice",
        tenant_id=_TENANT_A,
        roles=["agent.invoke"],
    )


# --------------------------------------------------------------------
# Scenario 17: cross-tenant get_run returns 404 + security event.
# --------------------------------------------------------------------


def test_scenario_17_cross_tenant_get_run_returns_404_and_fires_security_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A run that exists only on tenant_b is invisible to a tenant_a principal.

    The route returns 404 with run_not_found error_code and emits a
    TENANT_SCOPE_VIOLATION security event with the principal's tenant_id
    and the requested run_id logged for forensic correlation.
    """
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-iso-17")
    reader = _TenantScopedFakeReader()
    sec = _FakeSecurityEventLogger()
    # Seed a run on tenant_b only.
    tenant_b_run_id = uuid4()
    reader.put(_TENANT_B, _make_run_record_for_tenant(_TENANT_B, tenant_b_run_id))

    app = _build_app_with_tenant_a_context(reader=reader, security_events=sec)
    client = TestClient(app)

    response = client.get(
        f"/runs/{tenant_b_run_id}",
        headers={"Authorization": f"Bearer {_token_for_tenant_a()}"},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "run_not_found"
    assert str(tenant_b_run_id) in body["message"]
    assert body["correlation_id"]

    # The cross-tenant read fired a TENANT_SCOPE_VIOLATION security
    # event because the HTTP layer fires on every 404 from GET /runs/{id}
    # per D98.
    assert len(sec.events) == 1
    event = sec.events[0]
    assert event.category == SecurityEventCategory.TENANT_SCOPE_VIOLATION
    assert event.outcome == "not_found"
    assert event.metadata["requested_run_id"] == str(tenant_b_run_id)
    assert event.metadata["principal_tenant_id"] == _TENANT_A


# --------------------------------------------------------------------
# Scenario 18: cross-tenant list_runs returns empty + NO security event.
# --------------------------------------------------------------------


def test_scenario_18_cross_tenant_list_runs_returns_empty_no_security_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tenant-A principal with filters that would match tenant_b's runs sees empty.

    No security event fires because list-no-results is structurally
    indistinguishable from no-results-by-filter on the principal's
    own tenant. The asymmetry between specific-resource (404 fires
    security event) and broad-query (empty list does not) is the
    D98 commitment.
    """
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-iso-18")
    reader = _TenantScopedFakeReader()
    sec = _FakeSecurityEventLogger()
    # Seed a run on tenant_b only with a specific agent_template_id.
    target_template = uuid4()
    record = RunRecord(
        id=uuid4(),
        tenant_id=_TENANT_B,
        jurisdiction="eu-west",
        agent_template_id=target_template,
        agent_template_version=1,
        input_message="x",
        output_content="y",
        started_at=_NOW,
        completed_at=_NOW.replace(second=30),
        termination_reason="content",
        iteration_count=1,
        total_cost_usd=Decimal("0.001"),
        trace_id=None,
        audit_start_hash="a" * 64,
        audit_end_hash="b" * 64,
        created_at=_NOW.replace(second=30),
    )
    reader.put(_TENANT_B, record)

    app = _build_app_with_tenant_a_context(reader=reader, security_events=sec)
    client = TestClient(app)

    response = client.get(
        "/runs",
        params={"agent_template_id": str(target_template)},
        headers={"Authorization": f"Bearer {_token_for_tenant_a()}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["runs"] == []
    assert body["next_cursor"] is None
    # Critical: the empty list does NOT fire a security event.
    assert sec.events == []


# --------------------------------------------------------------------
# Scenario 19: missing principal returns 401.
# --------------------------------------------------------------------


def test_scenario_19_missing_principal_returns_401_no_security_event_on_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auth middleware fires before any route handler.

    Returns 401 from the middleware; no security event from the
    run-history routes themselves (the middleware fires AUTH_FAILURE
    separately at its own altitude per D26).
    """
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-iso-19")
    reader = _TenantScopedFakeReader()
    sec = _FakeSecurityEventLogger()
    app = _build_app_with_tenant_a_context(reader=reader, security_events=sec)
    client = TestClient(app)

    response_one = client.get(f"/runs/{uuid4()}")
    response_two = client.get("/runs")

    assert response_one.status_code == 401
    assert response_two.status_code == 401
    # No route-level security event fires; the middleware fires
    # AUTH_FAILURE at its own altitude via the file-backed logger,
    # which is not the same logger as the route-level
    # security_events override.
    assert sec.events == []
    # And the reader was never called.
    assert reader.get_run_calls == []
    assert reader.list_calls == []


# --------------------------------------------------------------------
# Scenario 20: principal's tenant not in registry returns 404
# (the brief said 401; reconciliation at session-open resolved to 404).
# --------------------------------------------------------------------


def test_scenario_20_principal_tenant_not_in_registry_returns_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reused get_tenant_context dep raises HTTPException 404.

    The S34 reconciliation finding (Appendix D, surface 1) resolved
    the brief's stated 401 to the existing 404 behaviour at
    apps/api/routers/inference.py:113-118; the run-history routes
    inherit cleanly. No security event from the run-history routes
    because the dependency fires before the handler.

    To exercise the real-registry path, we DO NOT override
    get_tenant_context. Instead we substitute the registry on
    app.state with a fake that returns None for the principal's
    tenant_id.
    """
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-iso-20")
    reader = _TenantScopedFakeReader()
    sec = _FakeSecurityEventLogger()

    class _NoSuchTenantRegistry:
        async def get_tenant(self, tenant_id):
            return None

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
    app.state.tenant_registry = _NoSuchTenantRegistry()
    app.dependency_overrides[get_run_history_reader] = lambda: reader
    app.dependency_overrides[get_security_event_logger] = lambda: sec
    app.state.security_events = sec
    client = TestClient(app)

    response = client.get(
        f"/runs/{uuid4()}",
        headers={"Authorization": f"Bearer {_token_for_tenant_a()}"},
    )

    # The get_tenant_context dependency raises HTTPException 404.
    # FastAPI's default HTTPException handler returns {"detail": str};
    # the run-history ErrorResponse handler is not registered for
    # HTTPException (only for the custom typed exceptions), so the
    # legacy shape applies. This is the as-built behaviour from D98
    # alternative (k) reasoning.
    assert response.status_code == 404
    # No route-level security event from the run-history routes; the
    # dependency fired before the handler.
    assert sec.events == []
    # The reader was never called.
    assert reader.get_run_calls == []
