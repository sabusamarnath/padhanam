"""HTTP contract tests for the portfolio read surface (D124, S43b).

Cursor-pagination canonicalisation (page boundaries; next_cursor
opacity and decode round-trip) and error-response body-shape
canonicalisation (every error path returns the D98 ErrorResponse
shape — error_code, message, correlation_id). Mirrors the S42
tests/contract/http/ precedent.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api._errors import register_portfolio_error_handlers
from apps.api.middleware import get_principal
from apps.api.routers import portfolio as portfolio_router
from apps.api.routers.inference import get_tenant_context
from contexts.portfolio.application.cursor import decode_case_cursor
from contexts.portfolio.domain import Case, CaseStatus, CaseType
from contexts.portfolio.domain.query_filters import CaseListCursor
from contexts.portfolio.ports import CaseListPage
from padhanam.security import Principal
from shared_kernel import TenantContext, TenantId

_TENANT_ID = "00000000-0000-4000-8000-00000000a001"
_BASE_TS = datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc)


def _ctx() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_ID, jurisdiction="eu-west",
        cost_attribution_id=_TENANT_ID,
    )


def _principal() -> Principal:
    return Principal(
        subject="alice", tenant_id=TenantId(_TENANT_ID),
        roles=frozenset({"portfolio.read"}), credential_ref="dev-token",
    )


def _case(i: int) -> Case:
    ts = _BASE_TS + timedelta(hours=i)
    return Case(
        id=uuid4(), tenant_id=UUID(_TENANT_ID), jurisdiction="eu-west",
        title=f"case {i}", case_type=CaseType.PORTFOLIO_ITEM,
        status=CaseStatus.OPEN, created_at=ts, updated_at=ts,
    )


class _PaginatingReader:
    """In-memory reader doing real (created_at DESC, id DESC) cursor
    pagination, mirroring the Postgres reader's ordering."""

    def __init__(self, cases: list[Case]) -> None:
        self._cases = cases

    async def list_cases(self, *, tenant_context, filters, cursor, page_size):
        rows = sorted(
            self._cases,
            key=lambda c: (c.created_at, str(c.id)),
            reverse=True,
        )
        if cursor is not None:
            key = (cursor.created_at, str(cursor.id))
            rows = [c for c in rows if (c.created_at, str(c.id)) < key]
        page = rows[:page_size]
        next_cursor = None
        if len(rows) > page_size:
            last = page[-1]
            next_cursor = CaseListCursor(
                created_at=last.created_at, id=last.id, page_size=page_size
            )
        return CaseListPage(cases=tuple(page), next_cursor=next_cursor)

    async def get_case(self, *, tenant_context, case_id):
        return None

    async def list_data_points(self, *, tenant_context, case_id):
        return ()

    async def get_data_point(self, *, tenant_context, data_point_id):
        return None

    async def assertion_history(self, *, tenant_context, data_point_id):
        return ()


class _NoopSecurityEvents:
    def emit(self, event: object) -> None:
        pass


def _client(reader: _PaginatingReader) -> TestClient:
    app = FastAPI()
    register_portfolio_error_handlers(app)
    app.include_router(portfolio_router.router)
    app.state.portfolio_reader = reader
    app.state.security_events = _NoopSecurityEvents()
    app.dependency_overrides[get_tenant_context] = _ctx
    app.dependency_overrides[get_principal] = _principal
    return TestClient(app)


def test_pagination_across_boundaries() -> None:
    client = _client(_PaginatingReader([_case(i) for i in range(3)]))

    page1 = client.get(
        "/api/v1/portfolio/cases", params={"page_size": 2}
    ).json()
    assert len(page1["cases"]) == 2
    assert page1["next_cursor"] is not None
    assert page1["cases"][0]["title"] == "case 2"  # newest first

    page2 = client.get(
        "/api/v1/portfolio/cases",
        params={"page_size": 2, "cursor": page1["next_cursor"]},
    ).json()
    assert len(page2["cases"]) == 1
    assert page2["next_cursor"] is None
    assert page2["cases"][0]["title"] == "case 0"


def test_next_cursor_is_opaque_and_decodes() -> None:
    client = _client(_PaginatingReader([_case(i) for i in range(3)]))
    next_cursor = client.get(
        "/api/v1/portfolio/cases", params={"page_size": 2}
    ).json()["next_cursor"]
    # opaque to the consumer — a base64 string — but the codec decodes it
    assert isinstance(next_cursor, str)
    decoded = decode_case_cursor(next_cursor)
    assert isinstance(decoded, CaseListCursor)
    assert decoded.page_size == 2


def test_error_response_body_shape_is_canonical() -> None:
    """Every portfolio error path returns the D98 ErrorResponse shape."""
    client = _client(_PaginatingReader([]))

    malformed = client.get(
        "/api/v1/portfolio/cases", params={"cursor": "not!base64!"}
    )
    assert malformed.status_code == 400
    for key in ("error_code", "message", "correlation_id"):
        assert key in malformed.json()

    invalid_filter = client.get(
        "/api/v1/portfolio/cases", params={"case_type": "BOGUS"}
    )
    assert invalid_filter.status_code == 400
    for key in ("error_code", "message", "correlation_id"):
        assert key in invalid_filter.json()
