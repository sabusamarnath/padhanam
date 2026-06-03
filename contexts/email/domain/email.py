"""Email — the stored email artefact (D151).

The persisted, encrypted, chunk-indexed record minted from a fetched
EmailMessage plus tenant context. A mutable-presence cache keyed on the
stable Gmail ``message_id``: full pulls upsert by content hash and
set-diff tombstones messages that left the window's live set (Gmail's
bounded query excludes Trash, so a trashed message simply stops appearing
— deletion is set-diff, not a status flag). Unlike calendar's Meeting,
email *content* is immutable once received, so an Email cites directly
with no citation-time snapshot (D151).

Sensitive content (subject, body, addresses, snippet) is P3 envelope-
encrypted at rest (D21); structural metadata (ids, received_at, labels,
history_id, content_hash) stays plaintext. ``to_search_text`` synthesises
subject + body for chunking and the content hash. Framework-free per D16.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from contexts.email.domain.email_message import EmailMessage


@dataclass(frozen=True)
class Email:
    id: UUID
    tenant_id: UUID
    jurisdiction: str
    message_id: str
    thread_id: str | None
    from_address: str | None
    to_addresses: tuple[str, ...]
    cc_addresses: tuple[str, ...]
    subject: str | None
    body: str | None
    snippet: str | None
    received_at: datetime | None
    labels: tuple[str, ...]
    history_id: str | None
    content_hash: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.jurisdiction or not self.jurisdiction.strip():
            raise ValueError("Email.jurisdiction must be non-empty")
        if not self.message_id or not self.message_id.strip():
            raise ValueError("Email.message_id must be non-empty")

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def to_search_text(self) -> str:
        return synthesise_email_text(subject=self.subject, body=self.body)


def synthesise_email_text(*, subject: str | None, body: str | None) -> str:
    """Subject + body, the text the chunker splits and the hash digests."""
    lines: list[str] = []
    if subject:
        lines.append(f"Subject: {subject}")
    if body:
        lines.append(body)
    return "\n\n".join(lines).strip()


def serialize_email_content(email: Email) -> bytes:
    """The D21-protected content (subject/body/addresses/snippet) as JSON bytes."""
    payload = {
        "subject": email.subject,
        "body": email.body,
        "snippet": email.snippet,
        "from_address": email.from_address,
        "to_addresses": list(email.to_addresses),
        "cc_addresses": list(email.cc_addresses),
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def email_from_message(
    message: EmailMessage,
    *,
    tenant_id: UUID,
    jurisdiction: str,
    email_id: UUID,
    now: datetime,
    created_at: datetime | None = None,
) -> Email:
    """Map a fetched EmailMessage to a stored Email; computes the content hash."""
    text = synthesise_email_text(subject=message.subject, body=message.body)
    return Email(
        id=email_id,
        tenant_id=tenant_id,
        jurisdiction=jurisdiction,
        message_id=message.google_message_id,
        thread_id=message.thread_id,
        from_address=message.from_address,
        to_addresses=message.to_addresses,
        cc_addresses=message.cc_addresses,
        subject=message.subject,
        body=message.body,
        snippet=message.snippet,
        received_at=message.received_at,
        labels=message.labels,
        history_id=message.history_id,
        content_hash=_content_hash(text),
        created_at=created_at or now,
        updated_at=now,
    )


__all__ = [
    "Email",
    "email_from_message",
    "serialize_email_content",
    "synthesise_email_text",
]
