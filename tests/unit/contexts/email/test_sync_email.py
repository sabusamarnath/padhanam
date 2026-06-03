"""Unit tests for the sync_email full-pull pipeline + set-diff deletion (D151)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from contexts.email.application.sync_email import sync_email
from contexts.email.domain.connection import Connection
from contexts.email.domain.email import email_from_message
from contexts.email.domain.email_message import EmailMessage, EmailMessageIdPage
from contexts.email.domain.errors import NoSuchConnectionError
from contexts.email.domain.sync_trigger import EmailSyncTrigger
from shared_kernel import TenantContext

_NOW = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)
_TENANT = "11111111-1111-1111-1111-111111111111"
_CONN = UUID("22222222-2222-2222-2222-222222222222")


def _ctx() -> TenantContext:
    return TenantContext(tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id="c")


def _connection() -> Connection:
    return Connection(
        id=_CONN, tenant_id=UUID(_TENANT), jurisdiction="eu-west", provider="google_mail",
        provider_config_key="google-mail", provider_connection_ref="ref",
        created_at=_NOW, updated_at=_NOW,
    )


def _msg(mid: str, *, subject: str = "Subject", body: str = "Body") -> EmailMessage:
    return EmailMessage(
        google_message_id=mid, thread_id="t1", from_address="a@x.com", to_addresses=("b@x.com",),
        cc_addresses=(), subject=subject, body=body, snippet="snip", received_at=_NOW,
        labels=("INBOX",), history_id="9",
    )


class _FakeSource:
    def __init__(self, *, messages: list[EmailMessage]) -> None:
        self._messages = messages
        self.list_calls = 0

    async def list_message_ids(self, *, connection, newer_than_days, page_token=None):
        self.list_calls += 1
        return EmailMessageIdPage(
            message_ids=tuple(m.google_message_id for m in self._messages), next_page_token=None
        )

    async def get_messages(self, *, connection, message_ids):
        return tuple(m for m in self._messages if m.google_message_id in set(message_ids))

    async def get_mailbox_history_id(self, *, connection):
        return "HID-123"


class _FakeConnRepo:
    def __init__(self, connection: Connection | None) -> None:
        self._connection = connection
        self.history_id: str | None = None

    async def get_connection(self, *, tenant_context, connection_id):
        return self._connection

    async def set_history_id(self, *, tenant_context, connection_id, history_id):
        self.history_id = history_id


class _FakeEmailStore:
    def __init__(self) -> None:
        self.by_id: dict[str, object] = {}
        self.tombstoned: list[str] = []

    async def upsert_email(self, *, tenant_context, email):
        self.by_id[email.message_id] = email

    async def tombstone_email(self, *, tenant_context, message_id, deleted_at):
        self.tombstoned.append(message_id)
        self.by_id.pop(message_id, None)

    async def get_by_message_id(self, *, tenant_context, message_id):
        return self.by_id.get(message_id)

    async def list_live_message_ids_in_window(self, *, tenant_context, window_start):
        return frozenset(self.by_id.keys())


def _run(source, conns, store):
    return asyncio.run(
        sync_email(
            tenant_context=_ctx(), connection_id=_CONN, trigger=EmailSyncTrigger.POLL,
            message_source=source, connections=conns, emails=store, email_reader=store, now=_NOW,
        )
    )


def test_full_pull_stores_and_anchors_history() -> None:
    source = _FakeSource(messages=[_msg("m1"), _msg("m2")])
    conns = _FakeConnRepo(_connection())
    store = _FakeEmailStore()
    result = _run(source, conns, store)
    assert result.mode == "full"
    assert result.upserted == 2
    assert set(result.changed_message_ids) == {"m1", "m2"}
    assert conns.history_id == "HID-123"  # dormant anchor stored
    assert set(store.by_id) == {"m1", "m2"}


def test_no_change_repull_is_noop() -> None:
    store = _FakeEmailStore()
    existing = email_from_message(
        _msg("m1", subject="Subject", body="Body"), tenant_id=UUID(_TENANT),
        jurisdiction="eu-west", email_id=uuid4(), now=_NOW,
    )
    store.by_id["m1"] = existing
    source = _FakeSource(messages=[_msg("m1", subject="Subject", body="Body")])
    result = _run(source, _FakeConnRepo(_connection()), store)
    assert "m1" not in result.changed_message_ids  # same content_hash -> no re-index
    assert store.by_id["m1"].id == existing.id  # id preserved


def test_set_diff_tombstones_removed_message() -> None:
    store = _FakeEmailStore()
    # Seed two stored, live messages; the pull returns only m1 (m2 trashed).
    for mid in ("m1", "m2"):
        store.by_id[mid] = email_from_message(
            _msg(mid), tenant_id=UUID(_TENANT), jurisdiction="eu-west", email_id=uuid4(), now=_NOW
        )
    source = _FakeSource(messages=[_msg("m1")])
    result = _run(source, _FakeConnRepo(_connection()), store)
    assert result.tombstoned == 1
    assert "m2" in store.tombstoned
    assert "m1" in store.by_id


def test_missing_connection_raises() -> None:
    with pytest.raises(NoSuchConnectionError):
        _run(_FakeSource(messages=[]), _FakeConnRepo(None), _FakeEmailStore())
