"""HTTP-level tenant isolation for the portfolio read surface (D24, D124, S43b).

The portfolio routes resolve tenant context from the principal; a
request authenticated as tenant B cannot read tenant A's case. The
adapter-level isolation (the bound-tenant defence-in-depth and the
``WHERE tenant_id`` scoping) is verified against synthetic databases at
``test_portfolio_isolation.py``; this file verifies the HTTP layer
resolves per-principal tenant context and that a cross-tenant case
lookup returns 404 plus a TENANT_SCOPE_VIOLATION security event, while
the same-tenant lookup succeeds.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api._errors import register_portfolio_error_handlers
from apps.api.middleware import get_actor_context
from apps.api.routers import portfolio as portfolio_router
from contexts.portfolio.domain import Case, CaseStatus, CaseType
from contexts.portfolio.ports import CaseListPage
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import authorisations_for_roles

_TENANT_A = "00000000-0000-4000-8000-00000000a001"
_TENANT_B = "00000000-0000-4000-8000-00000000b002"
_TS = datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc)


def _ctx(tenant_id: str) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id, jurisdiction="eu-west",
        cost_attribution_id=tenant_id,
    )


def _actor_context(tenant_id: str, subject: str) -> ActorContext:
    """A fully-authorised ActorContext for the given tenant.

    The authorisation set is complete — the decorator passes — so the
    404 a cross-tenant request receives is driven by tenant isolation
    alone, not by authorisation. The two dimensions are orthogonal.
    """
    role_list = frozenset({"operator"})
    return ActorContext(
        tenant_context=_ctx(tenant_id),
        actor_id=subject,
        role_list=role_list,
        authorisation_set=authorisations_for_roles(role_list),
    )


def _tenant_a_case() -> Case:
    return Case(
        id=uuid4(), tenant_id=UUID(_TENANT_A), jurisdiction="eu-west",
        title="Tenant A case", case_type=CaseType.PORTFOLIO_ITEM,
        status=CaseStatus.OPEN, created_at=_TS, updated_at=_TS,
    )


class _TenantScopedReader:
    """A reader holding one tenant-A case; cross-tenant reads return
    None / empty, mirroring the Postgres reader's tenant scoping."""

    def __init__(self, owner_tenant_id: str, case: Case) -> None:
        self._owner = owner_tenant_id
        self._case = case

    def _is_owner(self, tenant_context: TenantContext) -> bool:
        return str(tenant_context.tenant_id) == self._owner

    async def get_case(self, *, tenant_context, case_id):
        if self._is_owner(tenant_context) and case_id == self._case.id:
            return self._case
        return None

    async def list_cases(self, *, tenant_context, filters, cursor, page_size):
        cases = (self._case,) if self._is_owner(tenant_context) else ()
        return CaseListPage(cases=cases, next_cursor=None)

    async def list_data_points(self, *, tenant_context, case_id):
        return ()

    async def get_data_point(self, *, tenant_context, data_point_id):
        return None

    async def assertion_history(self, *, tenant_context, data_point_id):
        return ()


class _CollectingSecurityEvents:
    def __init__(self) -> None:
        self.events: list[object] = []

    def emit(self, event: object) -> None:
        self.events.append(event)


def _client(
    reader: _TenantScopedReader, tenant_id: str, subject: str
) -> tuple[TestClient, _CollectingSecurityEvents]:
    app = FastAPI()
    register_portfolio_error_handlers(app)
    app.include_router(portfolio_router.router)
    security_events = _CollectingSecurityEvents()
    app.state.portfolio_reader = reader
    app.state.security_events = security_events
    app.dependency_overrides[get_actor_context] = lambda: _actor_context(
        tenant_id, subject
    )
    return TestClient(app), security_events


def test_same_tenant_get_case_succeeds() -> None:
    case = _tenant_a_case()
    reader = _TenantScopedReader(_TENANT_A, case)
    client, _ = _client(reader, _TENANT_A, "alice")
    response = client.get(f"/api/v1/portfolio/cases/{case.id}")
    assert response.status_code == 200
    assert response.json()["case"]["id"] == str(case.id)


def test_cross_tenant_get_case_returns_404_plus_security_event() -> None:
    case = _tenant_a_case()
    reader = _TenantScopedReader(_TENANT_A, case)
    # tenant B's principal requests tenant A's case_id
    client, security_events = _client(reader, _TENANT_B, "bob")
    response = client.get(f"/api/v1/portfolio/cases/{case.id}")
    assert response.status_code == 404
    assert response.json()["error_code"] == "case_not_found"
    assert len(security_events.events) == 1


def test_same_tenant_list_returns_case() -> None:
    case = _tenant_a_case()
    reader = _TenantScopedReader(_TENANT_A, case)
    client, _ = _client(reader, _TENANT_A, "alice")
    response = client.get("/api/v1/portfolio/cases")
    assert response.status_code == 200
    assert len(response.json()["cases"]) == 1


def test_cross_tenant_list_returns_empty_no_security_event() -> None:
    case = _tenant_a_case()
    reader = _TenantScopedReader(_TENANT_A, case)
    client, security_events = _client(reader, _TENANT_B, "bob")
    response = client.get("/api/v1/portfolio/cases")
    assert response.status_code == 200
    assert response.json()["cases"] == []
    # list no-results fires no security event
    assert security_events.events == []


def test_actor_context_switch_does_not_weaken_tenant_isolation() -> None:
    """D126: the ActorContext carried into the use case is fully
    authorised — the decorator passes — yet the cross-tenant case
    lookup still returns 404. Authorisation and tenant isolation are
    orthogonal dimensions; the security event records the requester's
    tenant resolved from the ActorContext, not the target tenant."""
    case = _tenant_a_case()
    reader = _TenantScopedReader(_TENANT_A, case)
    client, security_events = _client(reader, _TENANT_B, "bob")

    response = client.get(f"/api/v1/portfolio/cases/{case.id}")

    assert response.status_code == 404
    assert len(security_events.events) == 1
    event = security_events.events[0]
    # the ActorContext's tenant_context drives the recorded tenant
    assert str(event.tenant_id) == _TENANT_B  # type: ignore[attr-defined]
    assert event.principal_ref == "bob"  # type: ignore[attr-defined]
