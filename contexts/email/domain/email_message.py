"""EmailMessage — provider-neutral domain shape for a fetched message (D151).

The two-call N+1 pull (D151) maps to two domain shapes: an
``EmailMessageIdPage`` (the ``users.messages.list`` stub page — ids plus
pagination, no content) and an ``EmailMessage`` (a parsed
``users.messages.get(format=full)`` result). Distinct from the stored
``Email`` artefact: an EmailMessage is the wire-to-domain DTO, an Email is
the persisted, encrypted, chunk-indexed artefact the pipeline mints from
it.

Unlike calendar's CalendarEvent there is no tombstone status — Gmail's
default query excludes Trash, so a trashed message simply does not appear
in the next pull (deletion is set-diff, D151), not a status flag.

No vendor types here (no-vendor-SDK-in-domain).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class EmailMessageIdPage:
    """One page of ``messages.list`` stubs: message ids plus the next cursor."""

    message_ids: tuple[str, ...]
    next_page_token: str | None = None


@dataclass(frozen=True)
class EmailMessage:
    """A parsed Gmail message (the ``messages.get(format=full)`` result)."""

    google_message_id: str
    thread_id: str | None
    from_address: str | None
    to_addresses: tuple[str, ...]
    cc_addresses: tuple[str, ...]
    subject: str | None
    body: str | None
    snippet: str | None
    received_at: datetime | None
    labels: tuple[str, ...] = field(default_factory=tuple)
    history_id: str | None = None

    def __post_init__(self) -> None:
        if not self.google_message_id or not self.google_message_id.strip():
            raise ValueError("EmailMessage.google_message_id must be non-empty")
