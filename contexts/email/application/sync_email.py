"""sync_email — the trigger-agnostic full-pull email pipeline (D151).

A function, not a Protocol (the calendar precedent), with one caller today
(the poll). Full-pull-only at Phase 2-A (the D149 lesson applied directly):
it drains the bounded window's message-id stubs, batch-fetches the full
messages, upserts each as an Email keyed on the Gmail message id, and
**set-diff tombstones** messages that left the window's live set (Gmail's
bounded query excludes Trash, so a trashed message simply stops appearing —
deletion is set-diff, not a status flag). The mailbox ``history_id`` (from
``getProfile``) is stored as the dormant future-incremental anchor; no
``history.list`` incremental path is built.

Indexing the changed Emails (body chunking + embedding + graph) is layered
on when the indexing tools are supplied — wired at commit 5; this function
reports which messages are new-or-content-changed so the indexing step
knows what to re-chunk.

Emits no audit events: per D155 the email store is an external-source
mutable cache, excluded from the audit-trail-as-source-of-truth principle;
its upsert/tombstone churn is not chained (email cites directly, so the
audited surface is the citation, not the cache write).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from contexts.email.application.index_email import index_email
from contexts.email.domain.email import Email, email_from_message
from contexts.email.domain.errors import NoSuchConnectionError
from contexts.email.domain.sync_trigger import EmailSyncTrigger
from contexts.email.ports.connection_repository import ConnectionRepository
from contexts.email.ports.email_index_ports import (
    EmailChunkEmbeddingPort,
    EmailGraphIndexPort,
)
from contexts.email.ports.email_message_source_port import EmailMessageSourcePort
from contexts.email.ports.email_repository import (
    EmailChunkRepository,
    EmailReader,
    EmailRepository,
)
from shared_kernel.tenant_context import TenantContext

_MAX_PAGES = 200


@dataclass(frozen=True)
class EmailSyncResult:
    mode: str  # "full" — the only mode under D151 full-pull-only
    fetched: int
    upserted: int
    tombstoned: int
    changed_message_ids: tuple[str, ...]
    history_id: str | None = None
    changed_emails: tuple[Email, ...] = field(default_factory=tuple)
    indexed: int = 0


async def sync_email(
    *,
    tenant_context: TenantContext,
    connection_id: UUID,
    trigger: EmailSyncTrigger,
    message_source: EmailMessageSourcePort,
    connections: ConnectionRepository,
    emails: EmailRepository,
    email_reader: EmailReader,
    embedder: EmailChunkEmbeddingPort | None = None,
    graph_index: EmailGraphIndexPort | None = None,
    chunks: EmailChunkRepository | None = None,
    window_days: int = 30,
    now: datetime | None = None,
) -> EmailSyncResult:
    """Pull, store, and set-diff-tombstone one email connection (full-pull, D151)."""
    del trigger  # recorded by the caller; no branch on it today
    now = now or datetime.now(timezone.utc)

    connection = await connections.get_connection(
        tenant_context=tenant_context, connection_id=connection_id
    )
    if connection is None:
        raise NoSuchConnectionError(str(connection_id))

    # Full pull: drain stub pages, then batch the full gets.
    message_ids: list[str] = []
    page_token: str | None = None
    for _ in range(_MAX_PAGES):
        page = await message_source.list_message_ids(
            connection=connection, newer_than_days=window_days, page_token=page_token
        )
        message_ids.extend(page.message_ids)
        if not page.next_page_token:
            break
        page_token = page.next_page_token

    messages = await message_source.get_messages(
        connection=connection, message_ids=message_ids
    )

    upserted = 0
    changed: list[str] = []
    changed_emails: list[Email] = []
    pulled_ids: set[str] = set()
    for message in messages:
        pulled_ids.add(message.google_message_id)
        existing = await email_reader.get_by_message_id(
            tenant_context=tenant_context, message_id=message.google_message_id
        )
        email = email_from_message(
            message,
            tenant_id=UUID(tenant_context.tenant_id),
            jurisdiction=tenant_context.jurisdiction,
            email_id=existing.id if existing is not None else uuid4(),
            now=now,
            created_at=existing.created_at if existing is not None else None,
        )
        await emails.upsert_email(tenant_context=tenant_context, email=email)
        upserted += 1
        if existing is None or existing.content_hash != email.content_hash:
            changed.append(message.google_message_id)
            changed_emails.append(email)

    # Set-diff deletion (D151): stored, non-deleted messages inside the
    # pull window that the pull did not return are trashed/deleted upstream.
    window_start = now - timedelta(days=window_days)
    stored_live = await email_reader.list_live_message_ids_in_window(
        tenant_context=tenant_context, window_start=window_start
    )
    tombstoned = 0
    for message_id in stored_live - pulled_ids:
        await emails.tombstone_email(
            tenant_context=tenant_context, message_id=message_id, deleted_at=now
        )
        tombstoned += 1

    # Index new-or-content-changed Emails into the inherited substrate when
    # the indexing tools are wired (apps/ composition): chunk the body,
    # embed the chunks, replace the message's chunk rows, and merge the
    # participant graph. A content change re-chunks and re-embeds.
    indexed = 0
    if embedder is not None and graph_index is not None and chunks is not None:
        for email in changed_emails:
            await index_email(
                tenant_context=tenant_context,
                email=email,
                embedder=embedder,
                graph_index=graph_index,
                chunks=chunks,
            )
            indexed += 1

    # Store the dormant mailbox history anchor (no incremental consumes it).
    history_id = await message_source.get_mailbox_history_id(connection=connection)
    if history_id is not None:
        await connections.set_history_id(
            tenant_context=tenant_context,
            connection_id=connection_id,
            history_id=history_id,
        )

    return EmailSyncResult(
        mode="full",
        fetched=len(messages),
        upserted=upserted,
        tombstoned=tombstoned,
        changed_message_ids=tuple(changed),
        history_id=history_id,
        changed_emails=tuple(changed_emails),
        indexed=indexed,
    )


__all__ = ["EmailSyncResult", "sync_email"]
