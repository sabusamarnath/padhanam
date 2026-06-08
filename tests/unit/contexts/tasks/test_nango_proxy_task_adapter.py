"""Unit tests for the Nango Proxy task adapter (D167).

httpx.MockTransport asserts request construction (the Bearer auth form Nango
requires; the Provider-Config-Key / Connection-Id headers; showCompleted/
showHidden/showDeleted=true on the full task pull; pagination) and response
mapping (200 page, auth -> config error, 5xx -> retryable error).

MockTransport's limit (the S55a lesson): these return author-populated bodies,
so they verify the adapter *parses* a shape, not what real Google *emits* — the
live operator-gated pull is the emit-side gate.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest

from contexts.tasks.adapters.outbound.nango.nango_proxy_task_adapter import (
    NangoProxyTaskAdapter,
)
from contexts.tasks.domain.connection import Connection
from contexts.tasks.domain.errors import (
    TaskSourceConfigurationError,
    TaskSourceError,
)

_T0 = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)


def _connection() -> Connection:
    return Connection(
        id=uuid4(),
        tenant_id=uuid4(),
        jurisdiction="eu-west",
        provider="google_tasks",
        provider_config_key="google-tasks",
        provider_connection_ref="conn-ref-123",
        created_at=_T0,
        updated_at=_T0,
    )


def _adapter(handler) -> tuple[NangoProxyTaskAdapter, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(_capture))
    return (
        NangoProxyTaskAdapter(
            base_url="http://localhost:3003",
            secret_key="sek_test",
            client=client,
        ),
        seen,
    )


def test_list_task_lists_parses_and_sends_headers() -> None:
    body = {
        "items": [
            {"id": "list-1", "title": "My Tasks"},
            {"id": "list-2", "title": "Work"},
        ],
        "nextPageToken": "tok2",
    }
    adapter, seen = _adapter(lambda req: httpx.Response(200, json=body))

    page = asyncio.run(adapter.list_task_lists(connection=_connection()))

    assert [tl.tasklist_id for tl in page.task_lists] == ["list-1", "list-2"]
    assert page.task_lists[1].title == "Work"
    assert page.next_page_token == "tok2"
    req = seen[0]
    assert req.url.path == "/proxy/tasks/v1/users/@me/lists"
    assert req.headers["Authorization"] == "Bearer sek_test"
    assert req.headers["Provider-Config-Key"] == "google-tasks"
    assert req.headers["Connection-Id"] == "conn-ref-123"


def test_list_tasks_parses_and_full_pull_params() -> None:
    body = {
        "items": [
            {
                "id": "t1",
                "title": "Apply to roles",
                "notes": "shortlist five",
                "status": "needsAction",
                "due": "2026-06-10T00:00:00.000Z",
                "position": "00000000000000000001",
                "updated": "2026-06-08T09:00:00.000Z",
            },
            {
                "id": "t2",
                "title": "Refresh CV",
                "status": "completed",
                "completed": "2026-06-07T12:00:00.000Z",
                "deleted": True,
            },
        ],
        "nextPageToken": None,
    }
    adapter, seen = _adapter(lambda req: httpx.Response(200, json=body))

    page = asyncio.run(
        adapter.list_tasks(connection=_connection(), tasklist_id="list-1")
    )

    assert [t.google_task_id for t in page.tasks] == ["t1", "t2"]
    assert page.tasks[0].title == "Apply to roles"
    assert page.tasks[0].status == "needsAction"
    assert page.tasks[1].is_tombstone is True  # deleted=true
    req = seen[0]
    assert req.url.path == "/proxy/tasks/v1/lists/list-1/tasks"
    params = dict(req.url.params)
    assert params["showCompleted"] == "true"
    assert params["showHidden"] == "true"
    assert params["showDeleted"] == "true"


def test_list_tasks_pagination_token_passed() -> None:
    adapter, seen = _adapter(
        lambda req: httpx.Response(200, json={"items": []})
    )
    asyncio.run(
        adapter.list_tasks(
            connection=_connection(), tasklist_id="list-1", page_token="PT"
        )
    )
    assert dict(seen[0].url.params)["pageToken"] == "PT"


def test_auth_failure_is_configuration_error() -> None:
    adapter, _ = _adapter(lambda req: httpx.Response(403, text="forbidden"))
    with pytest.raises(TaskSourceConfigurationError):
        asyncio.run(adapter.list_task_lists(connection=_connection()))


def test_server_error_is_retryable() -> None:
    adapter, _ = _adapter(lambda req: httpx.Response(503, text="unavailable"))
    with pytest.raises(TaskSourceError):
        asyncio.run(
            adapter.list_tasks(connection=_connection(), tasklist_id="l")
        )
