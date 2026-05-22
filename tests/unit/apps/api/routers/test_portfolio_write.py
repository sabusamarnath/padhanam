"""Route tests for the portfolio HTTP write surface (D127, D128, S44b).

A bare FastAPI app carries the portfolio router, the portfolio and
auth error handlers, and fakes on app.state; ``get_actor_context``
is dependency-overridden. The write routes drive the
intake-canonical orchestrations against the FakeIntakeRepository and
FakePortfolioWriter doubles.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api._auth_errors import register_auth_error_handlers
from apps.api._errors import register_portfolio_error_handlers
from apps.api.middleware import get_actor_context
from apps.api.routers import portfolio as portfolio_router
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import (
    ROLE_OPERATOR,
    authorisations_for_roles,
)
from tests.unit.contexts.intake.application._fakes import (
    FakeAuditPort,
    FakeIntakeRepository,
    FakePortfolioWriter,
)

_TENANT_ID = "00000000-0000-4000-8000-00000000a001"


def _tenant_context() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_ID,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_ID,
    )


def _actor_context(
    *, authorisation_set: frozenset[str] | None = None
) -> ActorContext:
    role_list = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=_tenant_context(),
        actor_id="operator",
        role_list=role_list,
        authorisation_set=(
            authorisations_for_roles(role_list)
            if authorisation_set is None
            else authorisation_set
        ),
    )


def _client(
    *,
    actor: ActorContext | None = None,
    writer: FakePortfolioWriter | None = None,
) -> tuple[TestClient, FakeIntakeRepository, FakePortfolioWriter]:
    app = FastAPI()
    register_portfolio_error_handlers(app)
    register_auth_error_handlers(app)
    app.include_router(portfolio_router.router)
    intake_repo = FakeIntakeRepository()
    portfolio_writer = writer or FakePortfolioWriter()
    app.state.intake_repository = intake_repo
    app.state.audit_port = FakeAuditPort()
    app.state.portfolio_writer = portfolio_writer
    app.dependency_overrides[get_actor_context] = lambda: (
        actor or _actor_context()
    )
    return TestClient(app), intake_repo, portfolio_writer


def test_post_cases_creates_intake_and_case() -> None:
    client, intake_repo, writer = _client()
    response = client.post(
        "/api/v1/portfolio/cases",
        json={"title": "Q3 board deck", "raw_text": "ship the deck"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Q3 board deck"
    assert "intake_id" in body and body["intake_id"] is not None
    # the intake was recorded; the case write carried its id
    assert len(intake_repo.intakes) == 1
    assert len(writer.created_cases) == 1
    intake = next(iter(intake_repo.intakes.values()))
    assert body["intake_id"] == str(intake.id)


def test_post_data_points_creates_intake_and_data_point() -> None:
    client, intake_repo, writer = _client()
    response = client.post(
        "/api/v1/portfolio/data_points",
        json={
            "case_id": str(uuid4()),
            "data_point_type": "GOAL",
            "value": {"progress": 0},
            "raw_text": "add a goal",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["data_point_type"] == "GOAL"
    assert body["intake_id"] is not None
    assert len(intake_repo.intakes) == 1
    assert len(writer.created_data_points) == 1


def test_patch_data_point_records_intake_and_revises() -> None:
    client, intake_repo, writer = _client()
    dp_id = uuid4()
    response = client.patch(
        f"/api/v1/portfolio/data_points/{dp_id}",
        json={"value": {"progress": 100}, "raw_text": "mark done"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data_point_id"] == str(dp_id)
    assert body["intake_id"] is not None
    assert len(intake_repo.intakes) == 1


def test_patch_unknown_data_point_returns_404() -> None:
    writer = FakePortfolioWriter()
    writer.raise_not_found = True
    client, _intake_repo, _writer = _client(writer=writer)
    response = client.patch(
        f"/api/v1/portfolio/data_points/{uuid4()}",
        json={"value": {}, "raw_text": "x"},
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "data_point_not_found"


def test_post_cases_denied_without_permission_returns_403() -> None:
    under = _actor_context(authorisation_set=frozenset())
    client, _intake_repo, _writer = _client(actor=under)
    response = client.post(
        "/api/v1/portfolio/cases",
        json={"title": "t", "raw_text": "x"},
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "authorisation_denied"


def test_post_cases_empty_raw_text_returns_422() -> None:
    client, _intake_repo, _writer = _client()
    response = client.post(
        "/api/v1/portfolio/cases",
        json={"title": "t", "raw_text": ""},
    )
    assert response.status_code == 422


def test_post_data_points_invalid_type_returns_422() -> None:
    client, _intake_repo, _writer = _client()
    response = client.post(
        "/api/v1/portfolio/data_points",
        json={
            "case_id": str(uuid4()),
            "data_point_type": "BOGUS",
            "value": {},
            "raw_text": "x",
        },
    )
    assert response.status_code == 422
