"""MeetingRepository / MeetingReader ports — the Meeting tenant store (D148).

The live Meeting row is a mutable search cache keyed on the Google event
id. The write side upserts modified events and tombstones cancelled ones;
the tombstone purges encrypted content and the vector (cancelled events
leave search) while retaining the row so a re-appearing event id is
recognised. The immutable evidence record is the audit snapshot, not this
store.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, Sequence

from contexts.calendar.domain.meeting import Meeting
from shared_kernel.tenant_context import TenantContext


class MeetingRepository(Protocol):
    async def upsert_meeting(
        self, *, tenant_context: TenantContext, meeting: Meeting
    ) -> None:
        """Insert or update a Meeting on (tenant_id, google_event_id)."""
        ...

    async def tombstone_meeting(
        self,
        *,
        tenant_context: TenantContext,
        google_event_id: str,
        cancelled_at: datetime,
    ) -> None:
        """Mark a Meeting CANCELLED, purging its content and vector.

        The row is retained keyed on the event id; only the encrypted
        content, the content hash, and the embedding are cleared so the
        cancelled event leaves search.
        """
        ...

    async def set_embedding(
        self,
        *,
        tenant_context: TenantContext,
        google_event_id: str,
        vector: Sequence[float],
    ) -> None:
        """Write the embedding vector for a stored Meeting (commit 6)."""
        ...


class MeetingReader(Protocol):
    async def get_by_event_id(
        self, *, tenant_context: TenantContext, google_event_id: str
    ) -> Meeting | None:
        """Return the stored Meeting for an event id, or None."""
        ...

    async def list_meetings(
        self, *, tenant_context: TenantContext, include_cancelled: bool = False
    ) -> tuple[Meeting, ...]:
        """List the tenant's stored Meetings (newest start first)."""
        ...
