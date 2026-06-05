"""Route tests for the Connections page status endpoint (D159, design-language §9).

A bare FastAPI app carries the connections router with a fake status
reader on app.state; ``get_actor_context`` is dependency-overridden.
Exercises the status DTO shape (calendar connect state + read-only scope +
domain tag; mail/Drive connectable-but-not-list-wired) and the 503 when
the reader is unconfigured.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api._connections_wiring import ConnectionsView, ConnectionStatus
from apps.api.middleware import get_actor_context
from apps.api.routers import connections as connections_router
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import authorisations_for_roles

_TENANT = "00000000-0000-4000-8000-00000000a001"


def _actor() -> ActorContext:
    roles = frozenset({"operator"})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
        ),
        actor_id="operator-001",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


class _FakeReader:
    def __init__(self, *, connected: bool) -> None:
        self._connected = connected

    async def status(self, *, actor) -> ConnectionsView:
        return ConnectionsView(
            calendar=ConnectionStatus(
                provider="google-calendar",
                name="Google Calendar",
                connected=self._connected,
                read_only_scope="calendar.readonly",
                domain_tag="work",
                list_wired=True,
            ),
            others=(
                ConnectionStatus(
                    provider="google-mail",
                    name="Gmail",
                    connected=False,
                    read_only_scope="gmail.readonly",
                    domain_tag=None,
                    list_wired=False,
                ),
            ),
        )


def _client(reader) -> TestClient:
    app = FastAPI()
    app.include_router(connections_router.router)
    if reader is not None:
        app.state.connections_status_reader = reader
    app.dependency_overrides[get_actor_context] = _actor
    return TestClient(app, raise_server_exceptions=False)


def test_connections_status_connected_shape() -> None:
    client = _client(_FakeReader(connected=True))
    res = client.get("/api/v1/connections")
    assert res.status_code == 200
    body = res.json()
    assert body["calendar"]["provider"] == "google-calendar"
    assert body["calendar"]["connected"] is True
    assert body["calendar"]["read_only_scope"] == "calendar.readonly"
    assert body["calendar"]["domain_tag"] == "work"
    assert body["calendar"]["list_wired"] is True
    # Mail renders as connectable but is not wired into the Today list.
    assert body["others"][0]["provider"] == "google-mail"
    assert body["others"][0]["list_wired"] is False


def test_connections_status_not_connected() -> None:
    client = _client(_FakeReader(connected=False))
    res = client.get("/api/v1/connections")
    assert res.status_code == 200
    assert res.json()["calendar"]["connected"] is False


def test_connections_status_503_when_unconfigured() -> None:
    client = _client(None)
    res = client.get("/api/v1/connections")
    assert res.status_code == 503
