"""HTTP-layer tenant-isolation scenarios for the ingestion routes (D24, D104, S38).

Six scenarios (34 through 39 in the D24 harness, extending S37's
33-scenario count to 39):

- **Scenario 34.** Tenant principal calling
  ``GET /ingestion/sources/{id}`` for another tenant's source
  returns 404 ``ingestion_source_not_found``. No security event
  fires — the per-tenant repository scopes the query by tenant_id,
  and at the single-source-lookup altitude cross-tenant invisibility
  is structurally indistinguishable from genuine not-found per the
  D104 commit-4 commentary on ingestion-source-not-found
  centralisation.

- **Scenario 35.** Tenant principal calling
  ``GET /ingestion/sources/{id}/status`` for another tenant's source
  returns 404 ``ingestion_source_not_found``. Mirror of scenario 34
  for the status projection route. No security event fires for the
  same reason.

- **Scenario 36.** Tenant principal calling
  ``GET /ingestion/sources`` returns own tenant's sources only.
  Cross-tenant sources in the repository are not present in the
  returned page.

- **Scenario 37.** Platform-operator-typed principal hitting
  ``GET /ingestion/sources`` returns 403 ``principal_type_mismatch``
  and fires an ``AUTHZ_DENIAL`` security event. The
  ``get_tenant_context`` dependency raises
  ``PrincipalTypeMismatchError``; the registered handler at
  ``apps/api/_auth_errors.py`` translates plus emits the event.

- **Scenario 38.** Unauthenticated request to ``GET /ingestion/sources``
  returns 401 from the auth middleware before any route handler runs.
  No route-level security event fires (the AUTH_FAILURE category
  fires from the middleware separately at its own altitude per D26).

- **Scenario 39.** ``GET /ingestion/sources?cursor=garbage`` returns
  400 ``malformed_ingestion_cursor`` from the query parser; the
  repository is never invoked.

The harness uses FastAPI's TestClient with selective
``dependency_overrides`` per scenario: where the auth dependency is
under test (scenario 37) we do NOT override ``get_tenant_context``
and instead exercise the real discriminator branch. Where the
repository's tenant-binding is under test (scenarios 34, 35, 36) we
override ``get_tenant_context`` with a tenant_a fixture.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from apps.api.main import AppCompositions, create_app
from apps.api.routers.ingestion import get_source_repository
from apps.api.routers.inference import get_tenant_context
from contexts.ingestion.domain.source import Source
from contexts.ingestion.domain.source_list import (
    SourceListCursor,
    SourceListPage,
)
from contexts.ingestion.domain.state import SourceState
from padhanam.events import SynchronousEventBus
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
)
from padhanam.security.auth import (
    issue_dev_token,
    issue_platform_operator_dev_token,
)
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


def _make_source(*, source_id: UUID, tenant_id: str) -> Source:
    return Source(
        id=source_id,
        tenant_id=tenant_id,
        jurisdiction="eu-west",
        file_name=f"source-{source_id}.md",
        file_type="md",
        file_size_bytes=42,
        raw_content=b"# example",
        state=SourceState.INDEXED,
        parsing_error_text=None,
        created_by_user_id="user-1",
        created_at=_NOW,
        updated_at=_NOW,
    )


class _TenantScopedFakeRepository:
    """Returns sources only for the requested tenant_id.

    Sources keyed by (tenant_id, source_id); cross-tenant reads see
    None. Mirror of the audit isolation harness's
    ``_TenantScopedFakeReader``.
    """

    def __init__(self) -> None:
        self._sources: dict[tuple[str, UUID], Source] = {}
        self.get_calls: list[tuple[UUID, str]] = []
        self.list_calls: list[
            tuple[str, SourceListCursor | None, int]
        ] = []

    def put(self, tenant_id: str, source: Source) -> None:
        self._sources[(tenant_id, source.id)] = source

    async def get_source(
        self, source_id: UUID, tenant_id: str
    ) -> Source | None:
        self.get_calls.append((source_id, tenant_id))
        return self._sources.get((tenant_id, source_id))

    async def list_sources(
        self,
        *,
        tenant_id: str,
        cursor: SourceListCursor | None,
        page_size: int,
    ) -> SourceListPage:
        self.list_calls.append((tenant_id, cursor, page_size))
        visible = tuple(
            source
            for (t, _sid), source in self._sources.items()
            if t == tenant_id
        )
        return SourceListPage(sources=visible, next_cursor=None)


class _FakeSecurityEventLogger:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def emit(self, event: SecurityEvent) -> None:
        self.events.append(event)


class _StubInferencePort:
    def complete(self, messages, model, tenant_context, tools=()):
        raise AssertionError("inference path not exercised here")


def _build_app(
    *,
    repository: _TenantScopedFakeRepository,
    security_events: _FakeSecurityEventLogger,
    override_tenant_context: bool = True,
) -> Any:
    app = create_app(
        compositions=AppCompositions(
            inference_port=_StubInferencePort(),  # type: ignore[arg-type]
            event_bus=SynchronousEventBus(),
        ),
        configure_tracing=False,
    )
    app.dependency_overrides[get_source_repository] = lambda: repository
    if override_tenant_context:
        app.dependency_overrides[get_tenant_context] = (
            lambda: _tenant_a_context()
        )
    app.state.security_events = security_events
    return app


def _tenant_token(tenant_id: str = _TENANT_A) -> str:
    return issue_dev_token(
        subject="alice",
        tenant_id=tenant_id,
        roles=["ingestion.read"],
    )


def _platform_operator_token() -> str:
    return issue_platform_operator_dev_token(subject="ops-1")


# --------------------------------------------------------------------
# Scenario 34: cross-tenant get_source returns 404, no security event.
# --------------------------------------------------------------------


def test_scenario_34_cross_tenant_get_source_returns_404_no_security_event() -> None:
    repository = _TenantScopedFakeRepository()
    sec = _FakeSecurityEventLogger()
    tenant_b_source_id = uuid4()
    repository.put(
        _TENANT_B,
        _make_source(source_id=tenant_b_source_id, tenant_id=_TENANT_B),
    )

    app = _build_app(repository=repository, security_events=sec)
    client = TestClient(app)

    response = client.get(
        f"/ingestion/sources/{tenant_b_source_id}",
        headers={"Authorization": f"Bearer {_tenant_token()}"},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "ingestion_source_not_found"
    assert str(tenant_b_source_id) in body["message"]
    assert body["correlation_id"]
    # Repository was queried under tenant_a scope; no cross-tenant
    # leakage; no security event fires (privacy-preserving 404).
    assert repository.get_calls[0] == (tenant_b_source_id, _TENANT_A)
    assert sec.events == []


# --------------------------------------------------------------------
# Scenario 35: cross-tenant get_source_status returns 404.
# --------------------------------------------------------------------


def test_scenario_35_cross_tenant_get_source_status_returns_404() -> None:
    repository = _TenantScopedFakeRepository()
    sec = _FakeSecurityEventLogger()
    tenant_b_source_id = uuid4()
    repository.put(
        _TENANT_B,
        _make_source(source_id=tenant_b_source_id, tenant_id=_TENANT_B),
    )

    app = _build_app(repository=repository, security_events=sec)
    client = TestClient(app)

    response = client.get(
        f"/ingestion/sources/{tenant_b_source_id}/status",
        headers={"Authorization": f"Bearer {_tenant_token()}"},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "ingestion_source_not_found"
    assert sec.events == []


# --------------------------------------------------------------------
# Scenario 36: list_sources returns own-tenant only.
# --------------------------------------------------------------------


def test_scenario_36_list_sources_returns_own_tenant_only() -> None:
    repository = _TenantScopedFakeRepository()
    sec = _FakeSecurityEventLogger()
    own_source = _make_source(source_id=uuid4(), tenant_id=_TENANT_A)
    other_source = _make_source(source_id=uuid4(), tenant_id=_TENANT_B)
    repository.put(_TENANT_A, own_source)
    repository.put(_TENANT_B, other_source)

    app = _build_app(repository=repository, security_events=sec)
    client = TestClient(app)

    response = client.get(
        "/ingestion/sources",
        headers={"Authorization": f"Bearer {_tenant_token()}"},
    )

    assert response.status_code == 200
    body = response.json()
    returned_ids = {item["id"] for item in body["sources"]}
    assert returned_ids == {str(own_source.id)}
    assert str(other_source.id) not in returned_ids
    assert body["next_cursor"] is None
    # Repository invoked under tenant_a scope; no security event.
    assert repository.list_calls[0][0] == _TENANT_A
    assert sec.events == []


# --------------------------------------------------------------------
# Scenario 37: platform-operator token hitting /ingestion/* returns 403.
# --------------------------------------------------------------------


def test_scenario_37_platform_operator_on_ingestion_route_returns_403_with_security_event() -> None:
    """The get_tenant_context dependency raises
    PrincipalTypeMismatchError on the platform-operator-typed token;
    the handler at apps/api/_auth_errors.py (D104) translates to 403
    ``principal_type_mismatch`` and emits the AUTHZ_DENIAL security
    event with the attempted route."""
    repository = _TenantScopedFakeRepository()
    sec = _FakeSecurityEventLogger()
    app = _build_app(
        repository=repository,
        security_events=sec,
        # Don't override get_tenant_context — we want the real
        # discriminator branch to fire on the platform-operator token.
        override_tenant_context=False,
    )
    client = TestClient(app)

    response = client.get(
        "/ingestion/sources",
        headers={"Authorization": f"Bearer {_platform_operator_token()}"},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["error_code"] == "principal_type_mismatch"
    assert "tenant" in body["message"]
    assert "platform_operator" in body["message"]
    # AUTHZ_DENIAL fires with the attempted route and principal info.
    assert len(sec.events) == 1
    event = sec.events[0]
    assert event.category == SecurityEventCategory.AUTHZ_DENIAL
    assert event.action == "GET /ingestion/sources"
    assert event.outcome == "principal_type_mismatch"
    assert event.metadata["required_principal_type"] == "tenant"
    assert event.metadata["actual_principal_type"] == "platform_operator"
    # Repository was never invoked — discriminator gates upstream.
    assert repository.get_calls == []
    assert repository.list_calls == []


# --------------------------------------------------------------------
# Scenario 38: unauthenticated request returns 401.
# --------------------------------------------------------------------


def test_scenario_38_unauthenticated_request_returns_401() -> None:
    repository = _TenantScopedFakeRepository()
    sec = _FakeSecurityEventLogger()
    app = _build_app(repository=repository, security_events=sec)
    client = TestClient(app)

    response = client.get("/ingestion/sources")

    assert response.status_code == 401
    # Repository was never invoked.
    assert repository.get_calls == []
    assert repository.list_calls == []


# --------------------------------------------------------------------
# Scenario 39: malformed cursor returns 400.
# --------------------------------------------------------------------


def test_scenario_39_malformed_cursor_returns_400() -> None:
    repository = _TenantScopedFakeRepository()
    sec = _FakeSecurityEventLogger()
    app = _build_app(repository=repository, security_events=sec)
    client = TestClient(app)

    response = client.get(
        "/ingestion/sources?cursor=not!base64",
        headers={"Authorization": f"Bearer {_tenant_token()}"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "malformed_ingestion_cursor"
    # Parser failed before the repository was invoked.
    assert repository.list_calls == []
