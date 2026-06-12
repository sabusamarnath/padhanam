"""NangoProxyEmailAdapter — the single EmailMessageSourcePort adapter (D151).

Fetches Gmail messages through self-hosted Nango's Proxy over HTTP against
the google-mail provider (proxy base ``https://gmail.googleapis.com``,
``gmail.readonly``). The only place in the email context that speaks
Gmail's wire format or Nango Proxy's headers; everything Google- or
Nango-specific lives here (no-vendor-SDK-in-domain).

The pull is two-call (D151): ``list_message_ids`` pages the bounded
window's ``{id, threadId}`` stubs (``q=newer_than:<N>d``, which excludes
Trash/Spam), then ``get_messages`` fetches ``messages.get(format=full)``
per id under bounded concurrency (the per-message round-trip is the cost
centre; serial gets over thousands of ids is the failure mode, so a
semaphore caps in-flight gets). ``get_mailbox_history_id`` reads
``users.getProfile`` for the dormant incremental anchor.

Auth is ``Authorization: Bearer <secret>`` — Nango 0.70.5 rejects HTTP
Basic on the Proxy with a misleading ``not a UUID v4`` error (the calendar
finding); the Bearer form is load-bearing and pinned by a unit test.
"""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Sequence

import httpx

from contexts.email.domain.connection import Connection
from contexts.email.domain.email_message import EmailMessage, EmailMessageIdPage
from contexts.email.domain.errors import (
    EmailSourceConfigurationError,
    EmailSourceError,
)

_DEFAULT_MAX_RESULTS = 250
_DEFAULT_TIMEOUT = 30.0
_DEFAULT_GET_CONCURRENCY = 10


class NangoProxyEmailAdapter:
    """Single EmailMessageSourcePort adapter over Nango Proxy (google-mail)."""

    def __init__(
        self,
        *,
        base_url: str,
        secret_key: str,
        client: httpx.AsyncClient | None = None,
        max_results: int = _DEFAULT_MAX_RESULTS,
        get_concurrency: int = _DEFAULT_GET_CONCURRENCY,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._secret_key = secret_key
        self._client = client
        self._owns_client = client is None
        self._max_results = max_results
        self._get_concurrency = get_concurrency
        self._timeout = timeout

    def _headers(self, connection: Connection) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._secret_key}",
            "Provider-Config-Key": connection.provider_config_key,
            "Connection-Id": connection.provider_connection_ref,
        }

    async def _client_ctx(self) -> httpx.AsyncClient:
        return self._client or httpx.AsyncClient(timeout=self._timeout)

    # ----------------------------------------------------------- list stubs
    async def list_message_ids(
        self,
        *,
        connection: Connection,
        newer_than_days: int,
        query: str | None = None,
        page_token: str | None = None,
    ) -> EmailMessageIdPage:
        # D183: the optional scope is ANDed into the window bound (Gmail treats
        # a space as AND), so the job-search slice is fetched, not the whole
        # inbox. ``query`` is None for D151's general whole-window pull.
        q = f"newer_than:{newer_than_days}d"
        if query:
            q = f"{q} ({query})"
        params: dict[str, str] = {
            "q": q,
            "maxResults": str(self._max_results),
        }
        if page_token:
            params["pageToken"] = page_token
        url = f"{self._base_url}/proxy/gmail/v1/users/me/messages"
        client = await self._client_ctx()
        try:
            response = await client.get(url, params=params, headers=self._headers(connection))
        except httpx.HTTPError as exc:
            raise EmailSourceError(f"email proxy list failed: {exc}") from exc
        finally:
            if self._owns_client:
                await client.aclose()
        body = self._ok_json(response)
        messages = body.get("messages", []) or []
        return EmailMessageIdPage(
            message_ids=tuple(m["id"] for m in messages if m.get("id")),
            next_page_token=body.get("nextPageToken"),
        )

    # ----------------------------------------------------------- batched get
    async def get_messages(
        self, *, connection: Connection, message_ids: Sequence[str]
    ) -> tuple[EmailMessage, ...]:
        if not message_ids:
            return ()
        client = await self._client_ctx()
        sem = asyncio.Semaphore(self._get_concurrency)
        headers = self._headers(connection)

        async def _one(mid: str) -> EmailMessage | None:
            url = f"{self._base_url}/proxy/gmail/v1/users/me/messages/{mid}"
            async with sem:
                try:
                    resp = await client.get(
                        url, params={"format": "full"}, headers=headers
                    )
                except httpx.HTTPError as exc:
                    raise EmailSourceError(f"email proxy get failed: {exc}") from exc
            if resp.status_code == 404:
                # Message vanished between list and get (trashed/deleted) —
                # skip; set-diff handles its removal from the store.
                return None
            return _parse_message(self._ok_json(resp))

        try:
            results = await asyncio.gather(*[_one(m) for m in message_ids])
        finally:
            if self._owns_client:
                await client.aclose()
        return tuple(r for r in results if r is not None)

    # ----------------------------------------------------- history anchor
    async def get_mailbox_history_id(
        self, *, connection: Connection
    ) -> str | None:
        url = f"{self._base_url}/proxy/gmail/v1/users/me/profile"
        client = await self._client_ctx()
        try:
            resp = await client.get(url, headers=self._headers(connection))
        except httpx.HTTPError as exc:
            raise EmailSourceError(f"email proxy profile failed: {exc}") from exc
        finally:
            if self._owns_client:
                await client.aclose()
        body = self._ok_json(resp)
        hid = body.get("historyId")
        return str(hid) if hid is not None else None

    # ------------------------------------------------------ response mapping
    def _ok_json(self, response: httpx.Response) -> dict[str, Any]:
        status = response.status_code
        if status == 200:
            return response.json()
        if status in (400, 401, 403):
            raise EmailSourceConfigurationError(
                f"email proxy returned {status}: {response.text[:500]}"
            )
        raise EmailSourceError(
            f"email proxy returned {status}: {response.text[:500]}"
        )


# ---------------------------------------------------------------- parsing


def _b64url(data: str) -> str:
    """Decode a Gmail base64url body part to text (best-effort UTF-8)."""
    if not data:
        return ""
    padded = data + "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded).decode("utf-8", "replace")
    except (ValueError, TypeError):
        return ""


def _extract_body(payload: dict[str, Any]) -> str:
    """Walk the MIME tree for a text/plain body, falling back to text/html.

    Gmail nests parts; a single-part message carries ``payload.body.data``,
    a multipart one carries ``payload.parts[]``. Prefers text/plain.
    """
    plain: list[str] = []
    html: list[str] = []

    def _walk(part: dict[str, Any]) -> None:
        mime = part.get("mimeType", "")
        body = part.get("body", {}) or {}
        data = body.get("data")
        if data and mime == "text/plain":
            plain.append(_b64url(data))
        elif data and mime == "text/html":
            html.append(_b64url(data))
        for sub in part.get("parts", []) or []:
            _walk(sub)

    _walk(payload)
    if plain:
        return "\n".join(t for t in plain if t).strip()
    return "\n".join(t for t in html if t).strip()


def _addresses(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(a.strip() for a in value.split(",") if a.strip())


def _received_at(internal_date: str | None, date_header: str | None) -> datetime | None:
    if internal_date:
        try:
            return datetime.fromtimestamp(int(internal_date) / 1000, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            pass
    if date_header:
        try:
            parsed = parsedate_to_datetime(date_header)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except (TypeError, ValueError):
            return None
    return None


def _parse_message(raw: dict[str, Any]) -> EmailMessage:
    payload = raw.get("payload", {}) or {}
    headers = {
        h.get("name", "").lower(): h.get("value")
        for h in (payload.get("headers", []) or [])
    }
    return EmailMessage(
        google_message_id=raw["id"],
        thread_id=raw.get("threadId"),
        from_address=headers.get("from"),
        to_addresses=_addresses(headers.get("to")),
        cc_addresses=_addresses(headers.get("cc")),
        subject=headers.get("subject"),
        body=_extract_body(payload),
        snippet=raw.get("snippet"),
        received_at=_received_at(raw.get("internalDate"), headers.get("date")),
        labels=tuple(raw.get("labelIds", []) or []),
        history_id=str(raw["historyId"]) if raw.get("historyId") is not None else None,
    )


__all__ = ["NangoProxyEmailAdapter"]
