"""NangoProxyTaskAdapter — the single TaskSourcePort adapter (D167).

Fetches Google Tasks through self-hosted Nango's Proxy over HTTP, reusing the
connected Google provider with an added ``tasks.readonly`` scope. The only place
in the tasks context that speaks Google's wire format or Nango Proxy's headers;
everything Google- or Nango-specific lives here (no-vendor-SDK-in-domain, D4/D16).

Reconciled against the current Google Tasks API (2026-06-08):
  - task lists: ``GET tasks/v1/users/@me/lists`` → ``{items:[{id,title}], nextPageToken}``
  - tasks:      ``GET tasks/v1/lists/{tasklist}/tasks`` → ``{items:[Task], nextPageToken}``
  - pagination: ``pageToken`` / ``nextPageToken``, ``maxResults`` (default 20, max 100)
  - params:     ``showCompleted`` (default true), ``showHidden`` (default false),
                ``showDeleted`` (default false) — set all true for a complete
                cache refresh; a deleted task returns with ``deleted: true``.
  - scope:      ``https://www.googleapis.com/auth/tasks.readonly`` (read-only).
  - status:     ``needsAction`` | ``completed``; the API exposes no recurrence.

Nango routing: the ``google-tasks`` integration's base URL is
``https://tasks.googleapis.com``, so the proxy path is ``/proxy/tasks/v1/...``
(the calendar adapter's ``/proxy/calendar/v3/...`` precedent). The exact proxy
path is reconciled at the live smoke, not asserted from memory (the S55a
lesson). Auth is ``Authorization: Bearer <secret>`` — self-hosted Nango rejects
HTTP Basic on the Proxy (pinned by a unit test, the calendar precedent).
"""

from __future__ import annotations

from typing import Any

import httpx

from contexts.tasks.domain.connection import Connection
from contexts.tasks.domain.errors import (
    TaskSourceConfigurationError,
    TaskSourceError,
)
from contexts.tasks.domain.task_source import (
    SourceTask,
    SourceTaskList,
    TaskListPage,
    TaskPage,
)

_DEFAULT_MAX_RESULTS = 100
_DEFAULT_TIMEOUT = 30.0


class NangoProxyTaskAdapter:
    """Single TaskSourcePort adapter over Nango Proxy (D167)."""

    def __init__(
        self,
        *,
        base_url: str,
        secret_key: str,
        client: httpx.AsyncClient | None = None,
        max_results: int = _DEFAULT_MAX_RESULTS,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._secret_key = secret_key
        self._client = client
        self._owns_client = client is None
        self._max_results = max_results
        self._timeout = timeout

    def _headers(self, connection: Connection) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._secret_key}",
            "Provider-Config-Key": connection.provider_config_key,
            "Connection-Id": connection.provider_connection_ref,
        }

    async def list_task_lists(
        self,
        *,
        connection: Connection,
        page_token: str | None = None,
    ) -> TaskListPage:
        params: dict[str, str] = {"maxResults": str(self._max_results)}
        if page_token:
            params["pageToken"] = page_token
        url = f"{self._base_url}/proxy/tasks/v1/users/@me/lists"
        body = await self._get(url, params, connection)
        items = body.get("items", []) or []
        return TaskListPage(
            task_lists=tuple(
                SourceTaskList(tasklist_id=item["id"], title=item.get("title"))
                for item in items
            ),
            next_page_token=body.get("nextPageToken"),
        )

    async def list_tasks(
        self,
        *,
        connection: Connection,
        tasklist_id: str,
        page_token: str | None = None,
        show_completed: bool = True,
        show_hidden: bool = True,
        show_deleted: bool = True,
    ) -> TaskPage:
        params: dict[str, str] = {
            "maxResults": str(self._max_results),
            "showCompleted": "true" if show_completed else "false",
            "showHidden": "true" if show_hidden else "false",
            "showDeleted": "true" if show_deleted else "false",
        }
        if page_token:
            params["pageToken"] = page_token
        url = f"{self._base_url}/proxy/tasks/v1/lists/{tasklist_id}/tasks"
        body = await self._get(url, params, connection)
        items = body.get("items", []) or []
        return TaskPage(
            tasks=tuple(_parse_task(item, tasklist_id) for item in items),
            next_page_token=body.get("nextPageToken"),
        )

    async def _get(
        self, url: str, params: dict[str, str], connection: Connection
    ) -> dict[str, Any]:
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.get(
                url, params=params, headers=self._headers(connection)
            )
        except httpx.HTTPError as exc:  # network/timeout — retryable
            raise TaskSourceError(f"tasks proxy request failed: {exc}") from exc
        finally:
            if self._owns_client:
                await client.aclose()
        return self._handle_response(response)

    @staticmethod
    def _handle_response(response: httpx.Response) -> dict[str, Any]:
        status = response.status_code
        if status == 200:
            return response.json()
        if status in (400, 401, 403):
            raise TaskSourceConfigurationError(
                f"tasks proxy returned {status}: {response.text[:500]}"
            )
        # 5xx and anything else: treat as transient/retryable.
        raise TaskSourceError(
            f"tasks proxy returned {status}: {response.text[:500]}"
        )


def _parse_task(item: dict[str, Any], tasklist_id: str) -> SourceTask:
    return SourceTask(
        google_task_id=item["id"],
        tasklist_id=tasklist_id,
        status=(item.get("status") or "needsAction"),
        title=item.get("title"),
        notes=item.get("notes"),
        due=item.get("due"),
        completed=item.get("completed"),
        parent=item.get("parent"),
        position=item.get("position"),
        updated=item.get("updated"),
        deleted=bool(item.get("deleted", False)),
        hidden=bool(item.get("hidden", False)),
    )


__all__ = ["NangoProxyTaskAdapter"]
