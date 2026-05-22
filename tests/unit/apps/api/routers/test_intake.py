"""Route tests for the intake HTTP surface (D127, D128, S44b).

A bare FastAPI app carries the intake router, the intake and auth
error handlers, and fakes on app.state; ``get_actor_context`` is
dependency-overridden.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api._auth_errors import register_auth_error_handlers
from apps.api._errors import register_intake_error_handlers
from apps.api.middleware import get_actor_context
from apps.api.routers import intake as intake_router
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import (
    ROLE_OPERATOR,
    authorisations_for_roles,
)
from tests.unit.contexts.intake.application._fakes import (
    FakeAuditPort,
    FakeIntakeRepository,
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
    *, actor: ActorContext | None = None
) -> tuple[TestClient, FakeIntakeRepository]:
    app = FastAPI()
    register_intake_error_handlers(app)
    register_auth_error_handlers(app)
    app.include_router(intake_router.router)
    intake_repo = FakeIntakeRepository()
    app.state.intake_repository = intake_repo
    app.state.audit_port = FakeAuditPort()
    app.dependency_overrides[get_actor_context] = lambda: (
        actor or _actor_context()
    )
    return TestClient(app), intake_repo


def test_post_intakes_records_an_intake() -> None:
    client, intake_repo = _client()
    response = client.post(
        "/api/v1/intakes",
        json={"intake_source": "MANUAL_ENTRY", "raw_text": "noticed a gap"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["raw_text"] == "noticed a gap"
    assert body["intake_source"] == "MANUAL_ENTRY"
    assert len(intake_repo.intakes) == 1


def test_get_intake_returns_the_record() -> None:
    client, _intake_repo = _client()
    created = client.post(
        "/api/v1/intakes",
        json={"raw_text": "a thing"},
    ).json()
    response = client.get(f"/api/v1/intakes/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_unknown_intake_returns_404() -> None:
    client, _intake_repo = _client()
    response = client.get(f"/api/v1/intakes/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["error_code"] == "intake_not_found"


def test_list_intakes_returns_recorded_intakes() -> None:
    client, _intake_repo = _client()
    for i in range(3):
        client.post("/api/v1/intakes", json={"raw_text": f"intake {i}"})
    response = client.get("/api/v1/intakes")
    assert response.status_code == 200
    assert len(response.json()["intakes"]) == 3


def test_post_intakes_denied_without_permission_returns_403() -> None:
    under = _actor_context(authorisation_set=frozenset())
    client, _intake_repo = _client(actor=under)
    response = client.post("/api/v1/intakes", json={"raw_text": "x"})
    assert response.status_code == 403
    assert response.json()["error_code"] == "authorisation_denied"


def test_post_intakes_empty_raw_text_returns_422() -> None:
    client, _intake_repo = _client()
    response = client.post("/api/v1/intakes", json={"raw_text": ""})
    assert response.status_code == 422
