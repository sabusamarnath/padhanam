"""EmailRepository / EmailReader / EmailChunkRepository ports (D151).

The stored Email is a message-id-keyed cache. The write side upserts
modified messages and tombstones (set-diff) those that left the window's
live set — the tombstone purges encrypted content, the content hash, and
the message's chunks/embeddings while retaining the row. The reader
supports the set-diff (the live message ids currently stored in the
window) and conversation reads (S56b). The chunk repository owns the
email-local ``email_chunks`` store.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, Sequence
from uuid import UUID

from contexts.email.domain.email import Email
from contexts.email.domain.email_chunk import EmailChunk
from shared_kernel.tenant_context import TenantContext


class EmailRepository(Protocol):
    async def upsert_email(
        self, *, tenant_context: TenantContext, email: Email
    ) -> None:
        """Insert or update an Email on (tenant_id, message_id)."""
        ...

    async def tombstone_email(
        self,
        *,
        tenant_context: TenantContext,
        message_id: str,
        deleted_at: datetime,
    ) -> None:
        """Mark an Email deleted, purging encrypted content, hash, and chunks.

        The row is retained keyed on the message id (set-diff deletion,
        D151); only the encrypted content, the content hash, and the
        message's chunk rows + vectors are cleared so the message leaves
        search.
        """
        ...


class EmailReader(Protocol):
    async def get_by_message_id(
        self, *, tenant_context: TenantContext, message_id: str
    ) -> Email | None:
        """Return the stored Email for a message id, or None."""
        ...

    async def list_emails(
        self, *, tenant_context: TenantContext, include_deleted: bool = False
    ) -> tuple[Email, ...]:
        """List the tenant's stored Emails (newest received first)."""
        ...

    async def list_live_message_ids_in_window(
        self, *, tenant_context: TenantContext, window_start: datetime
    ) -> frozenset[str]:
        """Stored, non-deleted message ids with received_at >= window_start.

        The set-diff scope (D151): ids in this set but absent from the
        current pull are tombstoned.
        """
        ...


class EmailChunkRepository(Protocol):
    async def replace_chunks(
        self,
        *,
        tenant_context: TenantContext,
        email_id: UUID,
        message_id: str,
        chunks: Sequence[tuple[EmailChunk, Sequence[float]]],
    ) -> None:
        """Replace all chunks (encrypted text + vector) for a message."""
        ...

    async def delete_chunks_for_message(
        self, *, tenant_context: TenantContext, message_id: str
    ) -> None:
        """Delete all chunk rows for a message (on tombstone or re-chunk)."""
        ...
