"""Integration test — the portfolio read-surface lifecycle (D124, S43b).

Runs the create-case / create-data-point / revise-data-point use cases
against an in-memory composition, then exercises the HTTP read surface
(GET /cases, GET /cases/{case_id}) via TestClient over the same
FakeReader. End-to-end: use-case writes -> reader -> HTTP DTO, with the
Revisable Protocol's revision history surfacing in the case detail.
"""

from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api._errors import register_portfolio_error_handlers
from apps.api.middleware import get_principal
from apps.api.routers import portfolio as portfolio_router
from apps.api.routers.inference import get_tenant_context
from contexts.portfolio.application import (
    create_case,
    create_data_point,
    revise_data_point,
)
from contexts.portfolio.domain import DataPointType
from padhanam.security import Principal
from shared_kernel import ActorReference, TenantContext, TenantId
from tests.unit.contexts.portfolio.application._fakes import (
    FakeAuditPort,
    FakeReader,
    FakeRepository,
    FakeStore,
)

_TENANT_ID = "00000000-0000-4000-8000-00000000a001"
_ACTOR = ActorReference(user_id="operator")


def _ctx() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_ID,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_ID,
    )


def _principal() -> Principal:
    return Principal(
        subject="alice",
        tenant_id=TenantId(_TENANT_ID),
        roles=frozenset({"portfolio.read"}),
        credential_ref="dev-token",
    )


class _NoopSecurityEvents:
    def emit(self, event: object) -> None:
        pass


def _client(reader: FakeReader) -> TestClient:
    app = FastAPI()
    register_portfolio_error_handlers(app)
    app.include_router(portfolio_router.router)
    app.state.portfolio_reader = reader
    app.state.security_events = _NoopSecurityEvents()
    app.dependency_overrides[get_tenant_context] = _ctx
    app.dependency_overrides[get_principal] = _principal
    return TestClient(app)


def test_read_surface_lifecycle() -> None:
    store = FakeStore()
    repo = FakeRepository(store)
    audit = FakeAuditPort()
    reader = FakeReader(store)

    async def _seed():
        case = await create_case(
            tenant_context=_ctx(), repository=repo, audit_port=audit,
            actor=_ACTOR, title="Lifecycle case",
        )
        data_point = await create_data_point(
            tenant_context=_ctx(), repository=repo, audit_port=audit,
            actor=_ACTOR, case_id=case.id,
            data_point_type=DataPointType.GOAL, value={"progress": 0},
        )
        await revise_data_point(
            tenant_context=_ctx(), repository=repo, reader=reader,
            audit_port=audit, actor=_ACTOR, data_point_id=data_point.id,
            value={"progress": 80},
        )
        return case

    case = asyncio.run(_seed())
    client = _client(reader)

    list_resp = client.get("/api/v1/portfolio/cases")
    assert list_resp.status_code == 200
    assert any(c["id"] == str(case.id) for c in list_resp.json()["cases"])

    detail = client.get(f"/api/v1/portfolio/cases/{case.id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["case"]["id"] == str(case.id)
    assert len(body["data_points"]) == 1
    assertions = body["data_points"][0]["assertions"]
    assert [a["assertion_type"] for a in assertions] == [
        "INITIAL",
        "REVISION",
    ]
    assert body["data_points"][0]["current_value"] == {"progress": 80}

    # an audit event fired for each of the three writes
    assert [e.action_verb for e in audit.events] == [
        "portfolio.case.create",
        "portfolio.data_point.create",
        "portfolio.data_point.revise",
    ]
