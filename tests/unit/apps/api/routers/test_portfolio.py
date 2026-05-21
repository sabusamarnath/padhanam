"""Route tests for the portfolio HTTP read surface (D124, S43b; D126, S44a).

A bare FastAPI app carries the portfolio router, the portfolio error
handlers, and a fake reader on app.state; ``get_actor_context`` is
dependency-overridden to a fully-authorised ActorContext. No auth
middleware — the tests exercise the router and the error-response
shapes, not the authentication path.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api._errors import register_portfolio_error_handlers
from apps.api.middleware import get_actor_context
from apps.api.routers import portfolio as portfolio_router
from contexts.portfolio.domain import (
    Assertion,
    AssertionType,
    Case,
    CaseStatus,
    CaseType,
    DataPoint,
    DataPointType,
)
from contexts.portfolio.ports import CaseListPage
from shared_kernel import ActorContext, ActorReference, TenantContext
from shared_kernel.authorisation import authorisations_for_roles

_TENANT_ID = "00000000-0000-4000-8000-00000000a001"
_ACTOR = ActorReference(user_id="operator")
_TS = datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc)


def _tenant_context() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_ID,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_ID,
    )


def _actor_context() -> ActorContext:
    role_list = frozenset({"operator"})
    return ActorContext(
        tenant_context=_tenant_context(),
        actor_id="operator",
        role_list=role_list,
        authorisation_set=authorisations_for_roles(role_list),
    )


def _case() -> Case:
    return Case(
        id=uuid4(),
        tenant_id=UUID(_TENANT_ID),
        jurisdiction="eu-west",
        title="Q3 board deck",
        case_type=CaseType.PORTFOLIO_ITEM,
        status=CaseStatus.OPEN,
        created_at=_TS,
        updated_at=_TS,
    )


def _data_point(case_id: UUID) -> DataPoint:
    dp_id = uuid4()
    initial = Assertion(
        id=uuid4(),
        data_point_id=dp_id,
        tenant_id=UUID(_TENANT_ID),
        jurisdiction="eu-west",
        assertion_type=AssertionType.INITIAL,
        revises_assertion_id=None,
        value={"progress": 0},
        authored_by=_ACTOR,
        created_at=_TS,
    )
    revision = Assertion(
        id=uuid4(),
        data_point_id=dp_id,
        tenant_id=UUID(_TENANT_ID),
        jurisdiction="eu-west",
        assertion_type=AssertionType.REVISION,
        revises_assertion_id=initial.id,
        value={"progress": 60},
        authored_by=_ACTOR,
        created_at=_TS,
    )
    return DataPoint(
        id=dp_id,
        case_id=case_id,
        tenant_id=UUID(_TENANT_ID),
        jurisdiction="eu-west",
        data_point_type=DataPointType.GOAL,
        value={"progress": 0},
        authored_by=_ACTOR,
        created_at=_TS,
        assertions=(initial, revision),
    )


class _FakeReader:
    def __init__(self, cases, data_points_by_case) -> None:
        self._cases = cases
        self._dps = data_points_by_case

    async def get_case(self, *, tenant_context, case_id):
        return next((c for c in self._cases if c.id == case_id), None)

    async def list_cases(self, *, tenant_context, filters, cursor, page_size):
        return CaseListPage(
            cases=tuple(self._cases[:page_size]), next_cursor=None
        )

    async def get_data_point(self, *, tenant_context, data_point_id):
        for dps in self._dps.values():
            for dp in dps:
                if dp.id == data_point_id:
                    return dp
        return None

    async def list_data_points(self, *, tenant_context, case_id):
        return tuple(self._dps.get(case_id, []))

    async def assertion_history(self, *, tenant_context, data_point_id):
        dp = await self.get_data_point(
            tenant_context=tenant_context, data_point_id=data_point_id
        )
        return dp.assertions if dp is not None else ()


class _FakeSecurityEvents:
    def __init__(self) -> None:
        self.events: list[object] = []

    def emit(self, event: object) -> None:
        self.events.append(event)


def _client(reader: _FakeReader) -> tuple[TestClient, _FakeSecurityEvents]:
    app = FastAPI()
    register_portfolio_error_handlers(app)
    app.include_router(portfolio_router.router)
    security_events = _FakeSecurityEvents()
    app.state.portfolio_reader = reader
    app.state.security_events = security_events
    app.dependency_overrides[get_actor_context] = _actor_context
    return TestClient(app), security_events


def test_list_cases_returns_page() -> None:
    case = _case()
    client, _ = _client(_FakeReader([case], {}))
    response = client.get("/api/v1/portfolio/cases")
    assert response.status_code == 200
    body = response.json()
    assert len(body["cases"]) == 1
    assert body["cases"][0]["id"] == str(case.id)
    assert body["cases"][0]["title"] == "Q3 board deck"
    assert body["next_cursor"] is None


def test_get_case_returns_detail_with_revision_history() -> None:
    case = _case()
    dp = _data_point(case.id)
    client, _ = _client(_FakeReader([case], {case.id: [dp]}))
    response = client.get(f"/api/v1/portfolio/cases/{case.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["case"]["id"] == str(case.id)
    assert len(body["data_points"]) == 1
    assertions = body["data_points"][0]["assertions"]
    assert [a["assertion_type"] for a in assertions] == [
        "INITIAL",
        "REVISION",
    ]
    assert body["data_points"][0]["current_value"] == {"progress": 60}


def test_get_case_not_found_returns_404_error_shape() -> None:
    client, security_events = _client(_FakeReader([], {}))
    missing = uuid4()
    response = client.get(f"/api/v1/portfolio/cases/{missing}")
    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "case_not_found"
    assert "correlation_id" in body
    # the 404 fires a TENANT_SCOPE_VIOLATION security event
    assert len(security_events.events) == 1


def test_list_cases_malformed_cursor_returns_400() -> None:
    client, _ = _client(_FakeReader([], {}))
    response = client.get(
        "/api/v1/portfolio/cases", params={"cursor": "not!base64!"}
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "malformed_portfolio_cursor"


def test_list_cases_invalid_filter_returns_400() -> None:
    client, _ = _client(_FakeReader([], {}))
    response = client.get(
        "/api/v1/portfolio/cases", params={"status": "BOGUS"}
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "invalid_portfolio_filter"
