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
        """Insert or update a Meeting on (tenant_id, calendar_id, event_id)."""
        ...

    async def tombstone_meeting(
        self,
        *,
        tenant_context: TenantContext,
        calendar_id: str,
        google_event_id: str,
        cancelled_at: datetime,
    ) -> None:
        """Mark a Meeting CANCELLED, purging its content and vector.

        The row is retained keyed on (calendar_id, event_id); only the
        encrypted content, the content hash, and the embedding are cleared so
        the cancelled event leaves search. Scoped by calendar_id (D176) so a
        tombstone in one account never purges a colliding row in another.
        """
        ...

    async def set_embedding(
        self,
        *,
        tenant_context: TenantContext,
        calendar_id: str,
        google_event_id: str,
        vector: Sequence[float],
    ) -> None:
        """Write the embedding vector for a stored Meeting (D176-scoped)."""
        ...


class MeetingReader(Protocol):
    async def get_by_event_id(
        self,
        *,
        tenant_context: TenantContext,
        google_event_id: str,
        calendar_id: str | None = None,
    ) -> Meeting | None:
        """Return the stored Meeting for an event id, or None.

        When ``calendar_id`` is given (the sync write path), the lookup is
        scoped to that calendar's exact row; omitted (the read path) it
        resolves any calendar's copy of a shared event (D176).
        """
        ...

    async def list_meetings(
        self, *, tenant_context: TenantContext, include_cancelled: bool = False
    ) -> tuple[Meeting, ...]:
        """List the tenant's stored Meetings (newest start first)."""
        ...
