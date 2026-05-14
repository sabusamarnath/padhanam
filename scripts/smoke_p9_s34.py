"""Live-stack smoke script for the P9/S34 run-history HTTP read surface.

Runs inside the padhanam-api container with the full app composition,
substituting only the registry-dependent ``get_tenant_context``
dependency to bypass the empty tenant_registry (S30b carryover). The
substitution provides a TenantContext bound to tenant_a's data plane
so the production wiring (run_history_reader, session factory cache,
neo4j driver, all of it) reaches the real tenant_a Postgres for read
operations.

Eleven verification paths exercised plus two happy paths. Each
path's request and response is captured and printed.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.main import create_app
from apps.api.routers.inference import get_tenant_context
from contexts.run_history.adapters.outbound.postgres.reader import (
    PostgresRunHistoryReader,
)
from padhanam.security.auth import issue_dev_token
from shared_kernel import TenantContext, TenantId


_TENANT_A_DSN = (
    "postgresql+asyncpg://"
    f"{os.environ['POSTGRES_TENANT_A_USER']}:"
    f"{os.environ['POSTGRES_TENANT_A_PASSWORD']}"
    f"@postgres-tenant-a:5432/"
    f"{os.environ['POSTGRES_TENANT_A_DB']}"
)


_TENANT_A_UUID = "00000000-0000-4000-8000-00000000a001"
_KNOWN_RUN_S32 = UUID("2e86d393-96b8-4aca-a12f-ac09d7e35355")  # has citations
_KNOWN_RUN_S31 = UUID("aedbefba-ea30-49fd-bf2e-435e9a4d2375")  # no citations
_NONEXISTENT_RUN = UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")


def _tenant_a_context() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_A_UUID,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_A_UUID,
    )


async def _run_smoke() -> None:
    app = create_app(configure_tracing=False)
    # Bypass the empty tenant registry (S30b carryover):
    # 1. Override get_tenant_context to short-circuit to tenant_a.
    # 2. Replace app.state.run_history_reader with one wired directly
    #    against tenant_a's data plane (no session-factory cache,
    #    which would also go through the registry).
    app.dependency_overrides[get_tenant_context] = _tenant_a_context

    engine = create_async_engine(_TENANT_A_DSN)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def _direct_resolver(_tid: TenantId):
        return sessionmaker

    app.state.run_history_reader = PostgresRunHistoryReader(
        per_tenant_sessionmaker_resolver=_direct_resolver,
        bound_tenant_id=TenantId(_TENANT_A_UUID),
    )

    token = issue_dev_token(
        subject="alice", tenant_id=_TENANT_A_UUID, roles=["agent.invoke"]
    )
    headers = {"Authorization": f"Bearer {token}"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        # ---------------- Happy paths ----------------
        await _report(
            client,
            "HAPPY_PATH_1: GET /runs/{known_s32_run} with citations",
            method="GET",
            path=f"/runs/{_KNOWN_RUN_S32}",
            headers=headers,
        )
        await _report(
            client,
            "HAPPY_PATH_2: GET /runs?termination_reason=content (paginated, page_size=1)",
            method="GET",
            path="/runs",
            params=[("termination_reason", "content"), ("page_size", "1")],
            headers=headers,
        )

        # ---------------- Eleven verification paths ----------------
        await _report(
            client,
            "PATH_1: bad UUID path param -> 422 validation_error",
            method="GET",
            path="/runs/not-a-uuid",
            headers=headers,
        )
        await _report(
            client,
            "PATH_2: bad query param type (page_size=abc) -> 422 validation_error",
            method="GET",
            path="/runs",
            params={"page_size": "abc"},
            headers=headers,
        )
        await _report(
            client,
            "PATH_3: page_size out of bounds (999) -> 422 validation_error",
            method="GET",
            path="/runs",
            params={"page_size": "999"},
            headers=headers,
        )
        await _report(
            client,
            "PATH_4: malformed cursor -> 400 malformed_cursor",
            method="GET",
            path="/runs",
            params={"cursor": "not-a-real-cursor!"},
            headers=headers,
        )
        await _report(
            client,
            "PATH_5: started_at_after > started_at_before -> 400 invalid_filter_range",
            method="GET",
            path="/runs",
            params={
                "started_at_after": "2026-05-14T18:00:00+00:00",
                "started_at_before": "2026-05-14T12:00:00+00:00",
            },
            headers=headers,
        )
        await _report(
            client,
            "PATH_6: missing auth -> 401",
            method="GET",
            path=f"/runs/{_KNOWN_RUN_S32}",
            headers={},
        )
        await _report(
            client,
            "PATH_7: cross-tenant/missing run -> 404 + security event "
            "(empty run_id of nonexistent shape)",
            method="GET",
            path=f"/runs/{_NONEXISTENT_RUN}",
            headers=headers,
        )
        await _report(
            client,
            "PATH_8: known-run on principal's own tenant -> 200 "
            "(identical 404 shape would fire on cross-tenant; smoked above as PATH_7)",
            method="GET",
            path=f"/runs/{_KNOWN_RUN_S31}",
            headers=headers,
        )
        await _report(
            client,
            "PATH_10: method not allowed (POST /runs/{id}) -> 405",
            method="POST",
            path=f"/runs/{_KNOWN_RUN_S32}",
            headers=headers,
        )
        await _report(
            client,
            "PATH_11: cursor + filters combined -> 200 (filter-narrowed within cursor window)",
            method="GET",
            path="/runs",
            params={
                "cursor": _make_cursor(),
                "termination_reason": "content",
            },
            headers=headers,
        )

        # PATH_9 (unexpected exception / 500 internal_error) is
        # exercised by the integration test
        # test_get_run_returns_500_on_bound_tenant_mismatch; reproducing
        # it in the live stack requires inducing the defence-in-depth
        # failure deliberately. The handler shape and security-event
        # firing are verified by unit tests at tests/unit/apps/api/test_errors.py.
        print(
            "\nPATH_9: unexpected exception / 500 internal_error\n"
            "  Exercised in integration tests "
            "(tests/integration/api/test_run_history_routes.py::"
            "test_get_run_returns_500_on_bound_tenant_mismatch); the "
            "defence-in-depth path is not safely reproducible in the "
            "live stack without bypassing the route's principal check.\n"
        )


def _make_cursor() -> str:
    """Build a valid cursor pointing at the newer S32 run to paginate past."""
    from contexts.run_history.application.cursor import encode
    from contexts.run_history.domain.query_filters import RunListCursor

    return encode(
        RunListCursor(
            started_at=datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
            id=UUID(int=(1 << 128) - 1),
            page_size=10,
        )
    )


async def _report(
    client: httpx.AsyncClient,
    title: str,
    *,
    method: str,
    path: str,
    headers: dict[str, str],
    params: list[tuple[str, str]] | dict[str, str] | None = None,
) -> None:
    print(f"\n=== {title} ===")
    print(f"  {method} {path} params={params}")
    response = await client.request(
        method=method, url=path, params=params, headers=headers
    )
    print(f"  status={response.status_code}")
    if "x-correlation-id" in response.headers:
        print(f"  X-Correlation-Id={response.headers['x-correlation-id']}")
    try:
        body = response.json()
        # Truncate long happy-path bodies for readability.
        text = json.dumps(body, indent=2, default=str)
        if len(text) > 2000:
            text = text[:1900] + "\n  ... (truncated)"
        print(f"  body={text}")
    except Exception:
        print(f"  body={response.text[:500]}")


if __name__ == "__main__":
    os.environ.setdefault("LITELLM_MASTER_KEY", "sk-smoke-s34")
    asyncio.run(_run_smoke())
