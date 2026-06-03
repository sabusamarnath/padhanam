"""Shared fixtures for email-conversation unit tests (S56b)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from contexts.email.domain.email import Email

_TENANT = UUID("00000000-0000-4000-8000-00000000a001")


def make_email(
    *,
    subject: str,
    from_address: str = "sender@example.com",
    to_addresses: tuple[str, ...] = ("me@example.com",),
    received_at: datetime | None = None,
    body: str = "body text",
    message_id: str | None = None,
    now: datetime | None = None,
) -> Email:
    now = now or datetime(2026, 6, 2, 9, 0, tzinfo=timezone.utc)
    return Email(
        id=uuid4(),
        tenant_id=_TENANT,
        jurisdiction="eu-west",
        message_id=message_id or uuid4().hex,
        thread_id="t1",
        from_address=from_address,
        to_addresses=to_addresses,
        cc_addresses=(),
        subject=subject,
        body=body,
        snippet=body[:50],
        received_at=received_at or now,
        labels=("INBOX",),
        history_id="9",
        content_hash="h",
        created_at=now,
        updated_at=now,
    )
