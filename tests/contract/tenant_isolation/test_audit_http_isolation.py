"""HTTP-layer tenant-isolation scenarios for the audit routes (D24, D103, S37).

Six scenarios (21 through 26 in the D24 harness, extending S34's
20-scenario count to 26):

- **Scenario 21.** Cross-tenant ``GET /audit/events/{id}`` with a
  tenant-A principal asking for an event that lives only on tenant_b
  returns 404 ``audit_event_not_found``. No security event fires —
  per-tenant destination routing scopes the query by tenant context,
  and at the single-event lookup altitude cross-tenant invisibility
  is structurally indistinguishable from genuine not-found per the
  D103 commit-4 commentary on audit-event-not-found centralisation.

- **Scenario 22.** Tenant-typed principal hitting
  ``GET /platform/audit/events`` returns 403 ``principal_type_mismatch``
  and fires an ``AUTHZ_DENIAL`` security event. The
  ``get_platform_operator_principal`` dependency raises
  ``PrincipalTypeMismatchError``; the registered handler at
  ``apps/api/_errors.py`` translates plus emits the event.

- **Scenario 23.** Platform-operator-typed principal hitting
  ``GET /audit/events`` returns 403 ``principal_type_mismatch``
  and fires an ``AUTHZ_DENIAL`` security event. Mirror of scenario 22
  for the opposite direction.

- **Scenario 24.** Platform-operator-typed principal hitting
  ``GET /platform/audit/events`` succeeds — control-plane chain
  events are returned, no security event fires.

- **Scenario 25.** Unauthenticated request to either route tree
  returns 401 from the auth middleware before any route handler runs.
  No route-level security event fires (the AUTH_FAILURE category
  fires from the middleware separately at its own altitude per D26).

- **Scenario 26.** ``GET /audit/events?resource_id=X`` without
  ``resource_type=Y`` returns 400 ``invalid_audit_filter`` from the
  query parser; the reader is never invoked.

The harness uses FastAPI's TestClient with selective
``dependency_overrides`` per scenario: where the auth dependency is
under test (scenarios 22, 23) we do NOT override
``get_tenant_context`` / ``get_platform_operator_principal`` and
instead exercise the real discriminator branch. Where the reader's
tenant-binding is under test (scenario 21) we override
``get_tenant_context`` with a tenant_a fixture.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from apps.api.main import AppCompositions, create_app
from apps.api.middleware import get_platform_operator_principal
from apps.api.routers.audit import get_audit_event_reader
from apps.api.routers.inference import get_tenant_context
from contexts.audit.domain.audit_event_record import AuditEventRecord
from contexts.audit.domain.chain_integrity import ChainIntegrityVerification
from contexts.audit.domain.destination import AuditDestination
from contexts.audit.domain.query_filters import (
    AuditEventListCursor,
    AuditEventListFilters,
    AuditEventListPage,
)
from contexts.tenancy.domain.tenant import Tenant
from padhanam.events import SynchronousEventBus
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
)
from padhanam.security.auth import issue_dev_token, issue_platform_operator_dev_token
from shared_kernel import TenantContext


_TENANT_A = "00000000-0000-4000-8000-0000000000a1"
_TENANT_B = "00000000-0000-4000-8000-0000000000a2"
_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)
_HASH_A = "a" * 64
_HASH_B = "b" * 64


def _tenant_a_context() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_A,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_A,
    )


def _make_record(*, event_id: UUID, tenant_id: str) -> AuditEventRecord:
    return AuditEventRecord(
        id=event_id,
        tenant_id=tenant_id,
        actor="user:alice",
        jurisdiction="eu-west",
        timestamp=_NOW,
        action_verb="agent.invoke.start",
        resource_type="agent",
        resource_id="agent-1",
        before_state={},
        after_state={},
        correlation_id="corr-1",
        previous_event_hash=_HASH_A,
        this_event_hash=_HASH_B,
    )


class _TenantScopedFakeReader:
    """Returns events only for the bound tenant context.

    Per-tenant destination: events keyed by (tenant_id, event_id);
    cross-tenant reads see None. Control-plane destination: separate
    store keyed by event_id only.
    """

    def __init__(self) -> None:
        self._per_tenant: dict[tuple[str, UUID], AuditEventRecord] = {}
        self._control_plane: dict[UUID, AuditEventRecord] = {}
        self.get_calls: list[
            tuple[AuditDestination, UUID, TenantContext | None]
        ] = []
        self.list_calls: list[
            tuple[
                AuditDestination,
                AuditEventListFilters,
                AuditEventListCursor | None,
                int,
                TenantContext | None,
            ]
        ] = []

    def put_tenant(self, tenant_id: str, record: AuditEventRecord) -> None:
        self._per_tenant[(tenant_id, record.id)] = record

    def put_control_plane(self, record: AuditEventRecord) -> None:
        self._control_plane[record.id] = record

    async def get_audit_event(
        self,
        *,
        destination: AuditDestination,
        event_id: UUID,
        tenant_context: TenantContext | None,
    ) -> AuditEventRecord | None:
        self.get_calls.append((destination, event_id, tenant_context))
        if destination == "per_tenant":
            assert tenant_context is not None
            return self._per_tenant.get(
                (str(tenant_context.tenant_id), event_id)
            )
        return self._control_plane.get(event_id)

    async def list_audit_events_with_filters(
        self,
        *,
        destination: AuditDestination,
        filters: AuditEventListFilters,
        cursor: AuditEventListCursor | None,
        page_size: int,
        tenant_context: TenantContext | None,
    ) -> AuditEventListPage:
        self.list_calls.append(
            (destination, filters, cursor, page_size, tenant_context)
        )
        if destination == "per_tenant":
            assert tenant_context is not None
            tid = str(tenant_context.tenant_id)
            visible = tuple(
                r for (t, _eid), r in self._per_tenant.items() if t == tid
            )
        else:
            visible = tuple(self._control_plane.values())
        return AuditEventListPage(
            events=visible,
            next_cursor=None,
            chain_integrity=ChainIntegrityVerification(status="verified"),
        )

    async def verify_chain_segment(self, *, destination, events):
        raise AssertionError("verify_chain_segment not exercised at S37")


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
    reader: _TenantScopedFakeReader,
    security_events: _FakeSecurityEventLogger,
    override_tenant_context: bool = True,
    tenant_registry: Any = None,
) -> Any:
    app = create_app(
        compositions=AppCompositions(
            inference_port=_StubInferencePort(),  # type: ignore[arg-type]
            event_bus=SynchronousEventBus(),
        ),
        configure_tracing=False,
    )
    app.dependency_overrides[get_audit_event_reader] = lambda: reader
    if override_tenant_context:
        # Default fixture: tenant_a. Used by scenarios that don't
        # exercise the discriminator branch directly.
        app.dependency_overrides[get_tenant_context] = lambda: _tenant_a_context()
    if tenant_registry is not None:
        app.state.tenant_registry = tenant_registry
    app.state.security_events = security_events
    return app


def _tenant_token(tenant_id: str = _TENANT_A) -> str:
    return issue_dev_token(
        subject="alice",
        tenant_id=tenant_id,
        roles=["audit.read"],
    )


def _platform_operator_token() -> str:
    return issue_platform_operator_dev_token(subject="ops-1")


# --------------------------------------------------------------------
# Scenario 21: cross-tenant get_audit_event returns 404 (no security event).
# --------------------------------------------------------------------


def test_scenario_21_cross_tenant_get_audit_event_returns_404_no_security_event() -> None:
    """An event that exists only on tenant_b is invisible to a tenant_a principal.

    The route returns 404 ``audit_event_not_found``. No security event
    fires because the per-tenant destination structurally scopes the
    query and the indistinguishability of cross-tenant-not-visible
    versus genuinely-missing means a fire-on-every-404 policy would
    produce noise without forensic value (D103 commit-4 commentary).
    """
    reader = _TenantScopedFakeReader()
    sec = _FakeSecurityEventLogger()
    tenant_b_event_id = uuid4()
    reader.put_tenant(_TENANT_B, _make_record(event_id=tenant_b_event_id, tenant_id=_TENANT_B))

    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    response = client.get(
        f"/audit/events/{tenant_b_event_id}",
        headers={"Authorization": f"Bearer {_tenant_token()}"},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "audit_event_not_found"
    assert str(tenant_b_event_id) in body["message"]
    assert body["correlation_id"]
    # The reader was invoked with the tenant_a context (route reaches
    # the data layer) and returned None per the tenant scoping.
    assert reader.get_calls[0][0] == "per_tenant"
    assert reader.get_calls[0][2] == _tenant_a_context()
    # No security event from the route — privacy-preserving 404 shape.
    assert sec.events == []


# --------------------------------------------------------------------
# Scenario 22: tenant token hitting /platform/audit/* returns 403 + AUTHZ_DENIAL.
# --------------------------------------------------------------------


def test_scenario_22_tenant_token_on_platform_route_returns_403_with_security_event() -> None:
    """The get_platform_operator_principal dependency raises
    PrincipalTypeMismatchError on the tenant-typed token; the handler
    translates to 403 ``principal_type_mismatch`` and emits the
    AUTHZ_DENIAL security event with the attempted route and the
    principal's tenant_id."""
    reader = _TenantScopedFakeReader()
    sec = _FakeSecurityEventLogger()
    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    response = client.get(
        "/platform/audit/events",
        headers={"Authorization": f"Bearer {_tenant_token()}"},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["error_code"] == "principal_type_mismatch"
    assert "platform_operator" in body["message"]
    assert "tenant" in body["message"]
    # AUTHZ_DENIAL fires with the attempted route and principal info.
    assert len(sec.events) == 1
    event = sec.events[0]
    assert event.category == SecurityEventCategory.AUTHZ_DENIAL
    assert event.action == "GET /platform/audit/events"
    assert event.outcome == "principal_type_mismatch"
    assert event.metadata["required_principal_type"] == "platform_operator"
    assert event.metadata["actual_principal_type"] == "tenant"
    assert event.principal_ref == "alice"
    # Reader was never invoked — discriminator gates upstream.
    assert reader.get_calls == []
    assert reader.list_calls == []


# --------------------------------------------------------------------
# Scenario 23: platform-operator token hitting /audit/* returns 403 + AUTHZ_DENIAL.
# --------------------------------------------------------------------


def test_scenario_23_platform_operator_token_on_tenant_route_returns_403_with_security_event() -> None:
    """The get_tenant_context dependency rejects platform-operator tokens
    with PrincipalTypeMismatchError; same translation + same event
    surface as scenario 22 in the opposite direction."""
    reader = _TenantScopedFakeReader()
    sec = _FakeSecurityEventLogger()
    # IMPORTANT: do NOT override get_tenant_context here — we want the
    # real discriminator branch.
    app = _build_app(
        reader=reader,
        security_events=sec,
        override_tenant_context=False,
    )
    client = TestClient(app)

    response = client.get(
        "/audit/events",
        headers={"Authorization": f"Bearer {_platform_operator_token()}"},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["error_code"] == "principal_type_mismatch"
    assert "tenant" in body["message"]
    assert "platform_operator" in body["message"]
    assert len(sec.events) == 1
    event = sec.events[0]
    assert event.category == SecurityEventCategory.AUTHZ_DENIAL
    assert event.action == "GET /audit/events"
    assert event.metadata["required_principal_type"] == "tenant"
    assert event.metadata["actual_principal_type"] == "platform_operator"
    assert event.principal_ref == "ops-1"
    # The tenant_id on the security event is None because the
    # platform-operator principal carries the empty sentinel.
    assert event.tenant_id is None


# --------------------------------------------------------------------
# Scenario 24: platform-operator token on /platform/audit/* succeeds.
# --------------------------------------------------------------------


def test_scenario_24_platform_operator_token_on_platform_route_returns_200() -> None:
    """Happy path for the platform-operator surface end-to-end."""
    reader = _TenantScopedFakeReader()
    sec = _FakeSecurityEventLogger()
    cp_event_id = uuid4()
    reader.put_control_plane(_make_record(event_id=cp_event_id, tenant_id=""))

    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    response = client.get(
        "/platform/audit/events",
        headers={"Authorization": f"Bearer {_platform_operator_token()}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["events"]) == 1
    assert body["events"][0]["tenant_id"] == ""
    assert body["chain_integrity"]["status"] == "verified"
    # No security event for the happy path.
    assert sec.events == []
    # Reader invoked with control-plane destination, no tenant context.
    assert reader.list_calls[0][0] == "control_plane"
    assert reader.list_calls[0][4] is None


# --------------------------------------------------------------------
# Scenario 25: unauthenticated request returns 401, no route-level event.
# --------------------------------------------------------------------


def test_scenario_25_unauthenticated_request_returns_401_no_route_event() -> None:
    """Auth middleware fires before any route handler runs."""
    reader = _TenantScopedFakeReader()
    sec = _FakeSecurityEventLogger()
    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    response_tenant = client.get(f"/audit/events/{uuid4()}")
    response_platform = client.get(f"/platform/audit/events/{uuid4()}")

    assert response_tenant.status_code == 401
    assert response_platform.status_code == 401
    # No route-level security event — AUTH_FAILURE fires from the
    # middleware at its own altitude via the file-backed logger,
    # which is not the same logger as the route-level
    # security_events override on app.state.
    assert sec.events == []
    # Reader was never called.
    assert reader.get_calls == []
    assert reader.list_calls == []


# --------------------------------------------------------------------
# Scenario 26: resource_id without resource_type returns 400, reader untouched.
# --------------------------------------------------------------------


def test_scenario_26_resource_id_without_resource_type_returns_400() -> None:
    """The query parser raises InvalidAuditFilterError; the registered
    handler translates to 400 ``invalid_audit_filter``. The reader is
    never invoked because the parser short-circuits."""
    reader = _TenantScopedFakeReader()
    sec = _FakeSecurityEventLogger()
    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    response = client.get(
        "/audit/events?resource_id=agent-1",
        headers={"Authorization": f"Bearer {_tenant_token()}"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "invalid_audit_filter"
    assert "resource_id" in body["message"]
    # No security event — query validation is not an authorization event.
    assert sec.events == []
    # Reader never called.
    assert reader.get_calls == []
    assert reader.list_calls == []
