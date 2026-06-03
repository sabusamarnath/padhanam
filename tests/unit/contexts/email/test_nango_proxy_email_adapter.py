"""Unit tests for the Nango Proxy email adapter (D151).

httpx.MockTransport asserts the two-call shape (list stubs over the
window with q=newer_than; batched get(format=full) parsing the MIME tree),
the Bearer auth pin (Nango 0.70.5 rejects Basic), pagination, the 404-skip
on a vanished message, and the getProfile historyId anchor.
"""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest

from contexts.email.adapters.outbound.nango.nango_proxy_email_adapter import (
    NangoProxyEmailAdapter,
)
from contexts.email.domain.connection import Connection
from contexts.email.domain.errors import (
    EmailSourceConfigurationError,
    EmailSourceError,
)

_T0 = datetime(2026, 5, 1, tzinfo=timezone.utc)


def _connection() -> Connection:
    return Connection(
        id=uuid4(),
        tenant_id=uuid4(),
        jurisdiction="eu-west",
        provider="google_mail",
        provider_config_key="google-mail",
        provider_connection_ref="conn-ref-123",
        created_at=_T0,
        updated_at=_T0,
    )


def _b64url(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


def _adapter(handler) -> tuple[NangoProxyEmailAdapter, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(_capture))
    return (
        NangoProxyEmailAdapter(
            base_url="http://nango-server:3003", secret_key="sek_test", client=client
        ),
        seen,
    )


def test_list_message_ids_window_and_bearer() -> None:
    body = {
        "messages": [{"id": "m1", "threadId": "t1"}, {"id": "m2", "threadId": "t1"}],
        "nextPageToken": "PAGE2",
    }
    adapter, seen = _adapter(lambda req: httpx.Response(200, json=body))
    page = asyncio.run(
        adapter.list_message_ids(connection=_connection(), newer_than_days=30)
    )
    req = seen[0]
    assert req.url.path == "/proxy/gmail/v1/users/me/messages"
    assert req.headers["Authorization"] == "Bearer sek_test"
    assert not req.headers["Authorization"].startswith("Basic ")
    q = dict(req.url.params)
    assert q["q"] == "newer_than:30d"
    assert page.message_ids == ("m1", "m2")
    assert page.next_page_token == "PAGE2"


_FULL_MESSAGE = {
    "id": "m1",
    "threadId": "t1",
    "labelIds": ["INBOX", "IMPORTANT"],
    "snippet": "quarterly numbers attached",
    "historyId": "998877",
    "internalDate": str(int(datetime(2026, 5, 12, 9, 0, tzinfo=timezone.utc).timestamp() * 1000)),
    "payload": {
        "headers": [
            {"name": "Subject", "value": "Q2 board pack"},
            {"name": "From", "value": "chair@example.com"},
            {"name": "To", "value": "me@example.com, cfo@example.com"},
            {"name": "Cc", "value": "ea@example.com"},
        ],
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": _b64url("Board pack body text")}},
            {"mimeType": "text/html", "body": {"data": _b64url("<p>ignored html</p>")}},
        ],
    },
}


def test_get_messages_parses_full_and_prefers_plaintext() -> None:
    adapter, seen = _adapter(lambda req: httpx.Response(200, json=_FULL_MESSAGE))
    msgs = asyncio.run(
        adapter.get_messages(connection=_connection(), message_ids=["m1"])
    )
    assert seen[0].url.path == "/proxy/gmail/v1/users/me/messages/m1"
    assert dict(seen[0].url.params)["format"] == "full"
    m = msgs[0]
    assert m.subject == "Q2 board pack"
    assert m.from_address == "chair@example.com"
    assert m.to_addresses == ("me@example.com", "cfo@example.com")
    assert m.cc_addresses == ("ea@example.com",)
    assert m.body == "Board pack body text"  # plaintext preferred over html
    assert m.snippet == "quarterly numbers attached"
    assert m.labels == ("INBOX", "IMPORTANT")
    assert m.history_id == "998877"
    assert m.received_at == datetime(2026, 5, 12, 9, 0, tzinfo=timezone.utc)


def test_get_messages_batches_all_ids() -> None:
    adapter, seen = _adapter(
        lambda req: httpx.Response(200, json={**_FULL_MESSAGE, "id": req.url.path.rsplit("/", 1)[-1]})
    )
    ids = [f"m{i}" for i in range(25)]
    msgs = asyncio.run(adapter.get_messages(connection=_connection(), message_ids=ids))
    assert len(msgs) == 25  # all ids fetched (bounded-concurrency batch)
    assert len(seen) == 25


def test_get_messages_skips_404_vanished_message() -> None:
    def _handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/gone"):
            return httpx.Response(404, text="Not Found")
        return httpx.Response(200, json={**_FULL_MESSAGE, "id": "ok"})

    adapter, _ = _adapter(_handler)
    msgs = asyncio.run(
        adapter.get_messages(connection=_connection(), message_ids=["ok", "gone"])
    )
    assert {m.google_message_id for m in msgs} == {"ok"}  # 404 skipped


def test_get_mailbox_history_id_from_profile() -> None:
    adapter, seen = _adapter(
        lambda req: httpx.Response(200, json={"emailAddress": "me@x", "historyId": "555"})
    )
    hid = asyncio.run(adapter.get_mailbox_history_id(connection=_connection()))
    assert seen[0].url.path == "/proxy/gmail/v1/users/me/profile"
    assert hid == "555"


def test_auth_error_maps_to_configuration_error() -> None:
    adapter, _ = _adapter(lambda req: httpx.Response(403, text="forbidden"))
    with pytest.raises(EmailSourceConfigurationError):
        asyncio.run(
            adapter.list_message_ids(connection=_connection(), newer_than_days=30)
        )


def test_5xx_maps_to_retryable_error() -> None:
    adapter, _ = _adapter(lambda req: httpx.Response(503, text="busy"))
    with pytest.raises(EmailSourceError):
        asyncio.run(
            adapter.list_message_ids(connection=_connection(), newer_than_days=30)
        )
