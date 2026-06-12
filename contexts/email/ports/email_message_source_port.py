"""EmailMessageSourcePort — the outbound port the pull pipeline depends on (D151).

Two methods because the Gmail pull is two-call (D151): ``list_message_ids``
pages the bounded window's stubs, and ``get_messages`` fetches the full
content for a batch of ids (batched/concurrent — the per-message
round-trip is the cost centre). ``get_mailbox_history_id`` reads the
mailbox's current historyId from ``users.getProfile`` — the dormant
future-incremental anchor (the list response carries no historyId).

Implemented by exactly one adapter this phase
(``NangoProxyEmailAdapter``); the port exists for hexagonal layering, not
as a premature vendor-abstraction (the two-threshold rule — replaceability
is secured by the Connection model + self-hosting, IMAP defers to
Phase 2-B).
"""

from __future__ import annotations

from typing import Protocol, Sequence

from contexts.email.domain.connection import Connection
from contexts.email.domain.email_message import EmailMessage, EmailMessageIdPage


class EmailMessageSourcePort(Protocol):
    async def list_message_ids(
        self,
        *,
        connection: Connection,
        newer_than_days: int,
        query: str | None = None,
        page_token: str | None = None,
    ) -> EmailMessageIdPage:
        """One page of message-id stubs over the bounded window.

        Carries the Gmail search bound (``q=newer_than:<N>d``) and excludes
        Trash/Spam by default (deletion is set-diff per D151). The final
        page has ``next_page_token=None``.

        ``query`` is an optional opaque source-side scope ANDed into the
        window bound (D183): when set, only matching messages are listed
        (the job-search slice — ATS/recruiter senders + application subjects);
        when ``None`` the whole window is listed (D151's general pull, the
        signal-layer default). The caller, not the domain, supplies the
        scope string; the adapter composes it into the vendor query.
        """
        ...

    async def get_messages(
        self, *, connection: Connection, message_ids: Sequence[str]
    ) -> tuple[EmailMessage, ...]:
        """Fetch full content for a batch of message ids (batched/concurrent).

        ``users.messages.get(format=full)`` per id, run under bounded
        concurrency so thousands of ids do not serialise. Returns the
        parsed EmailMessages (order not guaranteed).
        """
        ...

    async def get_mailbox_history_id(
        self, *, connection: Connection
    ) -> str | None:
        """The mailbox's current historyId (``users.getProfile``).

        Stored as the dormant future-incremental anchor (D151); no
        incremental path consumes it this phase.
        """
        ...
