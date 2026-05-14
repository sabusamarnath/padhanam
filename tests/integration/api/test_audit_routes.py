"""Integration tests for the audit HTTP routes (D103, S37).

Uses FastAPI TestClient with dependency_overrides per the run-history
precedent at test_run_history_routes.py. The reader, tenant context,
and platform-operator principal are substituted via the
``get_audit_event_reader`` / ``get_tenant_context`` /
``get_platform_operator_principal`` dependencies.

Four routes covered with happy paths plus 404 / 503 / query-filter
edge cases. Cross-principal-type 403 scenarios land at commit 6's
tenant-isolation contract harness via the full auth stack.
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
from contexts.audit.application.cursor import encode as encode_cursor
from contexts.audit.domain.audit_event_record import AuditEventRecord
from contexts.audit.domain.chain_integrity import ChainIntegrityVerification
from contexts.audit.domain.destination import AuditDestination
from contexts.audit.domain.query_filters import (
    AuditEventListCursor,
    AuditEventListFilters,
    AuditEventListPage,
)
from padhanam.events import SynchronousEventBus
from padhanam.security import PlatformOperatorPrincipal
from padhanam.security.auth import issue_dev_token, issue_platform_operator_dev_token
from shared_kernel import TenantContext


_TENANT_UUID = "00000000-0000-4000-8000-0000000000a1"
_EVENT_UUID = "00000000-0000-4000-8000-0000000000c1"
_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)
_HASH_A = "a" * 64
_HASH_B = "b" * 64


def _tenant_context_fixture() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_UUID,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_UUID,
    )


def _platform_operator_principal_fixture() -> PlatformOperatorPrincipal:
    return PlatformOperatorPrincipal(
        subject="ops-1",
        credential_ref="dev-ops-1...",
    )


def _make_record(
    *,
    event_id: UUID | None = None,
    tenant_id: str = _TENANT_UUID,
) -> AuditEventRecord:
    return AuditEventRecord(
        id=event_id or UUID(_EVENT_UUID),
        tenant_id=tenant_id,
        actor="user:alice",
        jurisdiction="eu-west",
        timestamp=_NOW,
        action_verb="agent.invoke.start",
        resource_type="agent",
        resource_id="agent-1",
        before_state={},
        after_state={"input": "hi"},
        correlation_id="corr-1",
        previous_event_hash=_HASH_A,
        this_event_hash=_HASH_B,
    )


class _FakeReader:
    """Records calls and returns scripted responses."""

    def __init__(
        self,
        *,
        get_returns: AuditEventRecord | None = None,
        list_returns: AuditEventListPage | None = None,
    ) -> None:
        self.get_returns = get_returns
        self.list_returns = list_returns or AuditEventListPage(
            events=(),
            next_cursor=None,
            chain_integrity=ChainIntegrityVerification(status="partial"),
        )
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

    async def get_audit_event(
        self,
        *,
        destination: AuditDestination,
        event_id: UUID,
        tenant_context: TenantContext | None,
    ) -> AuditEventRecord | None:
        self.get_calls.append((destination, event_id, tenant_context))
        return self.get_returns

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
        return self.list_returns

    async def verify_chain_segment(self, *, destination, events):
        raise AssertionError("verify_chain_segment not exercised at S37")


def _build_app(*, reader: _FakeReader) -> Any:
    class _StubInferencePort:
        def complete(self, messages, model, tenant_context, tools=()):
            raise AssertionError("inference path not exercised by audit tests")

    app = create_app(
        compositions=AppCompositions(
            inference_port=_StubInferencePort(),  # type: ignore[arg-type]
            event_bus=SynchronousEventBus(),
        ),
        configure_tracing=False,
    )
    app.dependency_overrides[get_tenant_context] = lambda: _tenant_context_fixture()
    app.dependency_overrides[
        get_platform_operator_principal
    ] = lambda: _platform_operator_principal_fixture()
    app.dependency_overrides[get_audit_event_reader] = lambda: reader
    return app


def _tenant_token() -> str:
    return issue_dev_token(
        subject="alice",
        tenant_id=_TENANT_UUID,
        roles=["audit.read"],
    )


def _platform_operator_token() -> str:
    return issue_platform_operator_dev_token(subject="ops-1")


# --------------------------------------------------------------------
# Per-tenant routes — happy path.
# --------------------------------------------------------------------


def test_get_tenant_audit_event_returns_200_with_record() -> None:
    reader = _FakeReader(get_returns=_make_record())
    app = _build_app(reader=reader)
    client = TestClient(app)

    response = client.get(
        f"/audit/events/{_EVENT_UUID}",
        headers={"Authorization": f"Bearer {_tenant_token()}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == _EVENT_UUID
    assert body["tenant_id"] == _TENANT_UUID
    assert body["action_verb"] == "agent.invoke.start"
    assert body["after_state"] == {"input": "hi"}
    assert body["previous_event_hash"] == _HASH_A
    assert body["this_event_hash"] == _HASH_B
    # Verify the route reached the reader with destination=per_tenant.
    assert reader.get_calls[0][0] == "per_tenant"
    assert reader.get_calls[0][1] == UUID(_EVENT_UUID)
    assert reader.get_calls[0][2] == _tenant_context_fixture()


def test_list_tenant_audit_events_returns_200_with_page() -> None:
    page = AuditEventListPage(
        events=(_make_record(),),
        next_cursor=AuditEventListCursor(
            timestamp=_NOW, id=UUID(_EVENT_UUID), page_size=10
        ),
        chain_integrity=ChainIntegrityVerification(status="verified"),
    )
    reader = _FakeReader(list_returns=page)
    app = _build_app(reader=reader)
    client = TestClient(app)

    response = client.get(
        "/audit/events?action_verb=agent.invoke.start&page_size=10",
        headers={"Authorization": f"Bearer {_tenant_token()}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["events"]) == 1
    assert body["events"][0]["id"] == _EVENT_UUID
    assert body["chain_integrity"]["status"] == "verified"
    assert body["next_cursor"] is not None
    # Verify reader received the filter and destination
    dest, filters, _cursor, page_size, tctx = reader.list_calls[0]
    assert dest == "per_tenant"
    assert filters.action_verbs == ("agent.invoke.start",)
    assert page_size == 10
    assert tctx == _tenant_context_fixture()


# --------------------------------------------------------------------
# Per-tenant routes — 404 path.
# --------------------------------------------------------------------


def test_get_tenant_audit_event_returns_404_on_missing() -> None:
    reader = _FakeReader(get_returns=None)
    app = _build_app(reader=reader)
    client = TestClient(app)

    response = client.get(
        f"/audit/events/{_EVENT_UUID}",
        headers={"Authorization": f"Bearer {_tenant_token()}"},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "audit_event_not_found"
    assert _EVENT_UUID in body["message"]
    assert "correlation_id" in body


# --------------------------------------------------------------------
# Per-tenant routes — filter validation 400 paths.
# --------------------------------------------------------------------


def test_list_tenant_audit_events_400_on_resource_id_without_resource_type() -> None:
    reader = _FakeReader()
    app = _build_app(reader=reader)
    client = TestClient(app)

    response = client.get(
        "/audit/events?resource_id=agent-1",
        headers={"Authorization": f"Bearer {_tenant_token()}"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "invalid_audit_filter"
    assert "resource_id" in body["message"]
    assert reader.list_calls == []  # parser short-circuits before the reader


def test_list_tenant_audit_events_400_on_only_one_timestamp_bound() -> None:
    reader = _FakeReader()
    app = _build_app(reader=reader)
    client = TestClient(app)

    response = client.get(
        "/audit/events?timestamp_range_start=2026-05-01T00:00:00Z",
        headers={"Authorization": f"Bearer {_tenant_token()}"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "invalid_audit_filter"


def test_list_tenant_audit_events_400_on_malformed_cursor() -> None:
    reader = _FakeReader()
    app = _build_app(reader=reader)
    client = TestClient(app)

    response = client.get(
        "/audit/events?cursor=not-a-valid-cursor",
        headers={"Authorization": f"Bearer {_tenant_token()}"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "malformed_audit_cursor"


def test_list_tenant_audit_events_round_trips_cursor() -> None:
    cursor_in = AuditEventListCursor(
        timestamp=_NOW, id=UUID(_EVENT_UUID), page_size=5
    )
    encoded = encode_cursor(cursor_in)
    reader = _FakeReader()
    app = _build_app(reader=reader)
    client = TestClient(app)

    response = client.get(
        f"/audit/events?cursor={encoded}",
        headers={"Authorization": f"Bearer {_tenant_token()}"},
    )

    assert response.status_code == 200
    # The reader saw the decoded cursor
    assert reader.list_calls[0][2] == cursor_in


# --------------------------------------------------------------------
# Control-plane routes — happy path.
# --------------------------------------------------------------------


def test_get_platform_audit_event_returns_200_with_record() -> None:
    cp_record = _make_record(
        event_id=UUID(_EVENT_UUID), tenant_id=""  # control-plane sentinel
    )
    reader = _FakeReader(get_returns=cp_record)
    app = _build_app(reader=reader)
    client = TestClient(app)

    response = client.get(
        f"/platform/audit/events/{_EVENT_UUID}",
        headers={"Authorization": f"Bearer {_platform_operator_token()}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == _EVENT_UUID
    assert body["tenant_id"] == ""
    # Verify the route reached the reader with destination=control_plane and
    # no tenant_context.
    assert reader.get_calls[0][0] == "control_plane"
    assert reader.get_calls[0][2] is None


def test_list_platform_audit_events_returns_200_with_page() -> None:
    page = AuditEventListPage(
        events=(_make_record(tenant_id=""),),
        next_cursor=None,
        chain_integrity=ChainIntegrityVerification(status="verified"),
    )
    reader = _FakeReader(list_returns=page)
    app = _build_app(reader=reader)
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
    # No next_cursor when the page didn't fill
    assert body["next_cursor"] is None
    dest, _filters, _cursor, _page_size, tctx = reader.list_calls[0]
    assert dest == "control_plane"
    assert tctx is None


# --------------------------------------------------------------------
# 503 when reader is not wired.
# --------------------------------------------------------------------


def test_get_tenant_audit_event_returns_503_when_reader_not_wired() -> None:
    """The dependency raises HTTPException(503) when app.state lacks
    audit_event_reader; this exercises the same shape as the
    run-history precedent."""

    class _StubInferencePort:
        def complete(self, messages, model, tenant_context, tools=()):
            raise AssertionError("inference path not exercised by audit tests")

    app = create_app(
        compositions=AppCompositions(
            inference_port=_StubInferencePort(),  # type: ignore[arg-type]
            event_bus=SynchronousEventBus(),
        ),
        configure_tracing=False,
    )
    app.dependency_overrides[get_tenant_context] = lambda: _tenant_context_fixture()
    # Note: get_audit_event_reader NOT overridden, and audit_event_reader
    # is None on app.state from the narrow AppCompositions above.
    client = TestClient(app)

    response = client.get(
        f"/audit/events/{_EVENT_UUID}",
        headers={"Authorization": f"Bearer {_tenant_token()}"},
    )

    assert response.status_code == 503
