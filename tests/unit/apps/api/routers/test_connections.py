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


# ---------------------------------------------------------- connect (D160)
from apps.api._calendar_connect_wiring import (
    ConnectError,
    ConnectSession,
    StoredConnection,
)
from apps.api.routers.connections import (
    get_calendar_connect_initiator,
    get_connection_store,
)


def _connect_client(*, initiator=None, store=None) -> TestClient:
    app = FastAPI()
    app.include_router(connections_router.router)
    app.dependency_overrides[get_actor_context] = _actor
    if initiator is not None:
        app.dependency_overrides[get_calendar_connect_initiator] = lambda: initiator
    if store is not None:
        app.dependency_overrides[get_connection_store] = lambda: store
    return TestClient(app, raise_server_exceptions=False)


class _GatedInitiator:
    async def create_session(self, *, actor):
        raise ConnectError("operator-gated")


class _LiveInitiator:
    async def create_session(self, *, actor):
        return ConnectSession(
            provider_config_key="google-calendar",
            connect_url="https://nango/connect/x",
        )


class _Store:
    def __init__(self, *, synced: bool) -> None:
        self._synced = synced
        self.calls: list[str] = []

    async def store_connection(self, *, actor, provider_connection_ref):
        self.calls.append(provider_connection_ref)
        import uuid

        return StoredConnection(
            connection_id=uuid.uuid4(),
            synced=self._synced,
            sync_error=None if self._synced else "operator-gated sync",
        )


def test_initiate_operator_gated_returns_503() -> None:
    client = _connect_client(initiator=_GatedInitiator())
    res = client.post("/api/v1/connections/calendar/initiate")
    assert res.status_code == 503


def test_initiate_returns_session_when_wired() -> None:
    client = _connect_client(initiator=_LiveInitiator())
    res = client.post("/api/v1/connections/calendar/initiate")
    assert res.status_code == 200
    assert res.json()["connect_url"].startswith("https://nango/")


def test_callback_stores_connection_and_reports_sync() -> None:
    store = _Store(synced=True)
    client = _connect_client(store=store)
    res = client.post(
        "/api/v1/connections/calendar/callback",
        json={"provider_connection_ref": "nango-123"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["synced"] is True
    assert body["connection_id"]
    assert store.calls == ["nango-123"]


def test_callback_reports_operator_gated_sync() -> None:
    client = _connect_client(store=_Store(synced=False))
    res = client.post(
        "/api/v1/connections/calendar/callback",
        json={"provider_connection_ref": "nango-123"},
    )
    assert res.status_code == 200
    assert res.json()["synced"] is False
    assert res.json()["sync_error"]
