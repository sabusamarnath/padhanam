"""Integration tests for GET /runs/{run_id} and GET /runs (S34, D98).

Uses FastAPI TestClient with dependency_overrides per the existing
SSE-endpoint test pattern at test_agent_sse_endpoint.py. The reader,
tenant context, and security-event logger are substituted via the
``get_run_history_reader`` / ``get_tenant_context`` /
``get_security_event_logger`` dependencies.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.main import AppCompositions, create_app
from apps.api.routers.inference import get_tenant_context
from apps.api.routers.run_history import (
    get_run_history_reader,
    get_security_event_logger,
)
from contexts.run_history.application.cursor import (
    decode as decode_cursor,
    encode as encode_cursor,
)
from contexts.run_history.domain.citation_records import (
    ChunkCitationRecord,
    EntityCitationRecord,
)
from contexts.run_history.domain.query_filters import (
    PAGE_SIZE_CEILING,
    RunListCursor,
    RunListFilters,
)
from contexts.run_history.domain.run_record import RunRecord
from contexts.run_history.ports.reader import RunListPage
from padhanam.events import SynchronousEventBus
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
)
from padhanam.security.auth import issue_dev_token
from shared_kernel import TenantContext


_TENANT_UUID = "00000000-0000-4000-8000-0000000000a1"
_RUN_UUID = "00000000-0000-4000-8000-0000000000b1"
_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)


def _tenant_context_fixture() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_UUID,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_UUID,
    )


def _make_run_record(
    *,
    run_id: UUID | None = None,
    chunks: tuple[ChunkCitationRecord, ...] = (),
    entities: tuple[EntityCitationRecord, ...] = (),
) -> RunRecord:
    rid = run_id or UUID(_RUN_UUID)
    return RunRecord(
        id=rid,
        tenant_id=_TENANT_UUID,
        jurisdiction="eu-west",
        agent_template_id=uuid4(),
        agent_template_version=1,
        input_message="hi",
        output_content="hello",
        started_at=_NOW,
        completed_at=_NOW.replace(second=30),
        termination_reason="content",
        iteration_count=1,
        total_cost_usd=Decimal("0.001"),
        trace_id=None,
        audit_start_hash="a" * 64,
        audit_end_hash="b" * 64,
        created_at=_NOW.replace(second=30),
        chunk_citations=chunks,
        entity_citations=entities,
    )


class _FakeReader:
    """Records calls and returns scripted responses."""

    def __init__(
        self,
        *,
        get_run_returns: RunRecord | None = None,
        list_returns: RunListPage | None = None,
    ) -> None:
        self.get_run_returns = get_run_returns
        self.list_returns = list_returns or RunListPage(runs=(), next_cursor=None)
        self.get_run_calls: list[tuple[TenantContext, UUID]] = []
        self.list_calls: list[
            tuple[TenantContext, RunListFilters, RunListCursor | None]
        ] = []

    async def get_run(
        self, *, tenant_context: TenantContext, run_id: UUID
    ) -> RunRecord | None:
        self.get_run_calls.append((tenant_context, run_id))
        return self.get_run_returns

    async def list_runs_with_filters(
        self,
        *,
        tenant_context: TenantContext,
        filters: RunListFilters,
        cursor: RunListCursor | None,
    ) -> RunListPage:
        self.list_calls.append((tenant_context, filters, cursor))
        return self.list_returns


class _FakeSecurityEventLogger:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def emit(self, event: SecurityEvent) -> None:
        self.events.append(event)


def _build_app(
    *,
    reader: _FakeReader,
    security_events: _FakeSecurityEventLogger,
) -> Any:
    """Build the FastAPI app with substituted run-history dependencies."""

    class _StubInferencePort:
        def complete(self, messages, model, tenant_context, tools=()):  # noqa: D401
            raise AssertionError("inference path not exercised by run-history tests")

    app = create_app(
        compositions=AppCompositions(
            inference_port=_StubInferencePort(),  # type: ignore[arg-type]
            event_bus=SynchronousEventBus(),
        ),
        configure_tracing=False,
    )
    app.dependency_overrides[get_tenant_context] = lambda: _tenant_context_fixture()
    app.dependency_overrides[get_run_history_reader] = lambda: reader
    app.dependency_overrides[get_security_event_logger] = lambda: security_events
    # Exception handlers read security_events from app.state (not via
    # FastAPI dependencies), so substitute the app.state seam too.
    app.state.security_events = security_events
    return app


def _token() -> str:
    return issue_dev_token(
        subject="alice",
        tenant_id=_TENANT_UUID,
        roles=["agent.invoke"],
    )


# --------------------------------------------------------------------
# GET /runs/{run_id} — happy path.
# --------------------------------------------------------------------


def test_get_run_returns_200_with_aggregate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-run-history")
    chunk = ChunkCitationRecord(
        id=uuid4(),
        run_id=UUID(_RUN_UUID),
        chunk_id=uuid4(),
        tenant_id=_TENANT_UUID,
        jurisdiction="eu-west",
        chunk_excerpt="excerpt content",
        source_snapshot={"file_name": "doc.md"},
    )
    record = _make_run_record(chunks=(chunk,))
    reader = _FakeReader(get_run_returns=record)
    sec = _FakeSecurityEventLogger()
    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    response = client.get(
        f"/runs/{_RUN_UUID}",
        headers={"Authorization": f"Bearer {_token()}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == _RUN_UUID
    assert body["tenant_id"] == _TENANT_UUID
    assert body["termination_reason"] == "content"
    assert body["total_cost_usd"] == "0.001"
    assert len(body["chunk_citations"]) == 1
    assert body["chunk_citations"][0]["chunk_excerpt"] == "excerpt content"
    assert body["entity_citations"] == []
    assert reader.get_run_calls[0][1] == UUID(_RUN_UUID)
    assert sec.events == []  # no security event on happy path


# --------------------------------------------------------------------
# GET /runs/{run_id} — 404 with security event.
# --------------------------------------------------------------------


def test_get_run_returns_404_and_fires_security_event_on_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-run-history")
    reader = _FakeReader(get_run_returns=None)
    sec = _FakeSecurityEventLogger()
    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    response = client.get(
        f"/runs/{_RUN_UUID}",
        headers={"Authorization": f"Bearer {_token()}"},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "run_not_found"
    assert _RUN_UUID in body["message"]
    assert body["correlation_id"]  # populated from CorrelationIdMiddleware
    assert body["details"] is None
    # The response header carries the same correlation_id as the body.
    assert response.headers.get("x-correlation-id") == body["correlation_id"]
    assert len(sec.events) == 1
    event = sec.events[0]
    assert event.category == SecurityEventCategory.TENANT_SCOPE_VIOLATION
    assert event.principal_ref == "alice"
    assert event.resource_ref == _RUN_UUID
    assert event.action == f"GET /runs/{_RUN_UUID}"
    assert event.outcome == "not_found"
    assert event.metadata["requested_run_id"] == _RUN_UUID


# --------------------------------------------------------------------
# GET /runs/{run_id} — 422 on bad UUID path param.
# --------------------------------------------------------------------


def test_get_run_returns_422_on_bad_uuid_path_param(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-run-history")
    reader = _FakeReader()
    sec = _FakeSecurityEventLogger()
    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    response = client.get(
        "/runs/not-a-uuid",
        headers={"Authorization": f"Bearer {_token()}"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "validation_error"
    assert body["correlation_id"]
    assert "errors" in body["details"]
    assert reader.get_run_calls == []
    assert sec.events == []


# --------------------------------------------------------------------
# GET /runs/{run_id} — 401 when unauthenticated.
# --------------------------------------------------------------------


def test_get_run_returns_401_when_unauthenticated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-run-history")
    reader = _FakeReader()
    sec = _FakeSecurityEventLogger()
    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    response = client.get(f"/runs/{_RUN_UUID}")
    assert response.status_code == 401
    assert reader.get_run_calls == []


# --------------------------------------------------------------------
# GET /runs — happy path with no filters.
# --------------------------------------------------------------------


def test_list_runs_returns_200_with_empty_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-run-history")
    record_a = _make_run_record(run_id=uuid4())
    record_b = _make_run_record(run_id=uuid4())
    reader = _FakeReader(
        list_returns=RunListPage(runs=(record_a, record_b), next_cursor=None)
    )
    sec = _FakeSecurityEventLogger()
    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    response = client.get(
        "/runs",
        headers={"Authorization": f"Bearer {_token()}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["runs"]) == 2
    assert body["next_cursor"] is None
    # The reader was called with empty filters and no cursor.
    _, filters, cursor = reader.list_calls[0]
    assert filters == RunListFilters()
    assert cursor is None


# --------------------------------------------------------------------
# GET /runs — filters and cursor wiring.
# --------------------------------------------------------------------


def test_list_runs_threads_filters_through_to_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-run-history")
    reader = _FakeReader()
    sec = _FakeSecurityEventLogger()
    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    tid = uuid4()
    response = client.get(
        "/runs",
        params=[
            ("agent_template_id", str(tid)),
            ("agent_template_version", "1"),
            ("termination_reason", "content"),
        ],
        headers={"Authorization": f"Bearer {_token()}"},
    )

    assert response.status_code == 200
    _, filters, _ = reader.list_calls[0]
    assert filters.agent_template_ids == (tid,)
    assert filters.agent_template_versions == (1,)
    assert filters.termination_reasons == ("content",)


def test_list_runs_encodes_next_cursor_when_reader_returns_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-run-history")
    record = _make_run_record(run_id=uuid4())
    next_cursor = RunListCursor(
        started_at=_NOW, id=record.id, page_size=PAGE_SIZE_CEILING
    )
    reader = _FakeReader(
        list_returns=RunListPage(runs=(record,), next_cursor=next_cursor)
    )
    sec = _FakeSecurityEventLogger()
    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    response = client.get(
        "/runs",
        headers={"Authorization": f"Bearer {_token()}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["next_cursor"] is not None
    # The encoded cursor round-trips through the codec.
    decoded = decode_cursor(body["next_cursor"])
    assert decoded.started_at == next_cursor.started_at
    assert decoded.id == next_cursor.id
    assert decoded.page_size == next_cursor.page_size


def test_list_runs_decodes_inbound_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-run-history")
    reader = _FakeReader()
    sec = _FakeSecurityEventLogger()
    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    inbound = RunListCursor(started_at=_NOW, id=uuid4(), page_size=10)
    encoded = encode_cursor(inbound)
    response = client.get(
        "/runs",
        params={"cursor": encoded},
        headers={"Authorization": f"Bearer {_token()}"},
    )

    assert response.status_code == 200
    _, _, cursor = reader.list_calls[0]
    assert cursor is not None
    assert cursor.id == inbound.id
    assert cursor.page_size == inbound.page_size


def test_list_runs_returns_401_when_unauthenticated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-run-history")
    reader = _FakeReader()
    sec = _FakeSecurityEventLogger()
    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    response = client.get("/runs")
    assert response.status_code == 401
    assert reader.list_calls == []


# --------------------------------------------------------------------
# Error handlers: malformed cursor, invalid filter range, page_size
# out of bounds, bound-tenant-id defence-in-depth, method not allowed.
# --------------------------------------------------------------------


def test_list_runs_returns_400_on_malformed_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-run-history")
    reader = _FakeReader()
    sec = _FakeSecurityEventLogger()
    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    response = client.get(
        "/runs",
        params={"cursor": "not-a-valid-cursor"},
        headers={"Authorization": f"Bearer {_token()}"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "malformed_cursor"
    assert body["correlation_id"]
    assert reader.list_calls == []


def test_list_runs_returns_400_on_only_one_date_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-run-history")
    reader = _FakeReader()
    sec = _FakeSecurityEventLogger()
    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    response = client.get(
        "/runs",
        params={"started_at_after": _NOW.isoformat()},
        headers={"Authorization": f"Bearer {_token()}"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "invalid_filter_range"
    assert "both be provided" in body["message"]


def test_list_runs_returns_400_on_inverted_date_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-run-history")
    reader = _FakeReader()
    sec = _FakeSecurityEventLogger()
    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    after = _NOW.replace(hour=18).isoformat()
    before = _NOW.replace(hour=12).isoformat()
    response = client.get(
        "/runs",
        params={"started_at_after": after, "started_at_before": before},
        headers={"Authorization": f"Bearer {_token()}"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "invalid_filter_range"
    assert "strictly earlier" in body["message"]


def test_list_runs_returns_422_on_page_size_out_of_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-run-history")
    reader = _FakeReader()
    sec = _FakeSecurityEventLogger()
    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    response = client.get(
        "/runs",
        params={"page_size": 999},
        headers={"Authorization": f"Bearer {_token()}"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "validation_error"
    assert body["correlation_id"]


def test_list_runs_returns_422_on_negative_page_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-run-history")
    reader = _FakeReader()
    sec = _FakeSecurityEventLogger()
    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    response = client.get(
        "/runs",
        params={"page_size": 0},
        headers={"Authorization": f"Bearer {_token()}"},
    )

    assert response.status_code == 422


def test_get_run_returns_500_on_bound_tenant_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reader's defence-in-depth ValueError translates to 500 plus
    a synchronous TENANT_SCOPE_VIOLATION security event with critical
    severity metadata per D98."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-run-history")

    class _RaisingReader(_FakeReader):
        async def get_run(self, *, tenant_context, run_id):  # type: ignore[override]
            raise ValueError(
                "TenantContext.tenant_id does not match adapter's bound tenant"
            )

    reader = _RaisingReader()
    sec = _FakeSecurityEventLogger()
    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    response = client.get(
        f"/runs/{_RUN_UUID}",
        headers={"Authorization": f"Bearer {_token()}"},
    )

    assert response.status_code == 500
    body = response.json()
    assert body["error_code"] == "internal_error"
    assert body["correlation_id"]
    assert len(sec.events) == 1
    event = sec.events[0]
    assert event.category == SecurityEventCategory.TENANT_SCOPE_VIOLATION
    assert event.outcome == "defence_in_depth_fired"
    assert event.metadata["severity"] == "critical"


def test_correlation_id_header_returned_on_happy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CorrelationIdMiddleware sets X-Correlation-Id on every response."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-run-history")
    record = _make_run_record()
    reader = _FakeReader(get_run_returns=record)
    sec = _FakeSecurityEventLogger()
    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    response = client.get(
        f"/runs/{_RUN_UUID}",
        headers={"Authorization": f"Bearer {_token()}"},
    )

    assert response.status_code == 200
    correlation_id = response.headers.get("x-correlation-id")
    assert correlation_id is not None
    # uuid4-shaped
    UUID(correlation_id)


def test_method_not_allowed_returns_405(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /runs/{run_id} is not registered; FastAPI default 405 shape applies."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-run-history")
    reader = _FakeReader()
    sec = _FakeSecurityEventLogger()
    app = _build_app(reader=reader, security_events=sec)
    client = TestClient(app)

    response = client.post(
        f"/runs/{_RUN_UUID}",
        headers={"Authorization": f"Bearer {_token()}"},
    )

    assert response.status_code == 405
