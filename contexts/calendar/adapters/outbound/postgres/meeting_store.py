"""Postgres adapter for the Meeting tenant store (D148).

Implements ``MeetingRepository`` (write) and ``MeetingReader`` (read)
against per-tenant Postgres data planes per D32, with bound-tenant-id
defence-in-depth (D24). Meeting content is field-level encrypted via P3
envelope encryption (D21): the structured content (title/description/
location/attendees/organizer) is serialized to JSON, encrypted under a
fresh DEK wrapped by the KEK, and stored in the five ``enc_*`` columns;
the AAD binds the ciphertext to ``tenant_id`` + the content field so it
cannot be replayed across tenants or fields.

The pgvector embedding cast happens at the SQL boundary (no pgvector
Python binding), mirroring ingestion's chunk-embedding write. SQLAlchemy
2.0 Core, manual row mapping, no ORM.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Protocol, Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from padhanam.security import crypto
from shared_kernel import TenantContext, TenantId

from contexts.calendar.adapters.outbound.postgres._tables import (
    meetings as meetings_table,
)
from contexts.calendar.domain.meeting import (
    Meeting,
    MeetingAttendee,
    MeetingStatus,
)

_CONTENT_FIELD = "meeting_content"


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


def _aad_context(tenant_id: object) -> dict[str, str]:
    return {"tenant_id": str(tenant_id), "field": _CONTENT_FIELD}


def serialize_meeting_content(meeting: Meeting) -> bytes:
    payload = {
        "title": meeting.title,
        "description": meeting.description,
        "location": meeting.location,
        "organizer_email": meeting.organizer_email,
        "attendees": [
            {
                "email": a.email,
                "display_name": a.display_name,
                "response_status": a.response_status,
                "organizer": a.organizer,
            }
            for a in meeting.attendees
        ],
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def deserialize_meeting_content(plaintext: bytes) -> dict[str, Any]:
    return json.loads(plaintext.decode("utf-8"))


def _format_vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"


def _row_to_meeting(row: dict[str, Any], *, tenant_id: object) -> Meeting:
    if row["enc_ciphertext"] is not None:
        field = crypto.EncryptedField(
            wrapped_dek=bytes(row["enc_wrapped_dek"]),
            dek_wrap_nonce=bytes(row["enc_dek_wrap_nonce"]),
            ciphertext=bytes(row["enc_ciphertext"]),
            nonce=bytes(row["enc_nonce"]),
            key_version=int(row["enc_key_version"]),
        )
        content = deserialize_meeting_content(
            crypto.decrypt_field(field, _aad_context(tenant_id))
        )
        attendees = tuple(
            MeetingAttendee(
                email=a.get("email"),
                display_name=a.get("display_name"),
                response_status=a.get("response_status"),
                organizer=bool(a.get("organizer", False)),
            )
            for a in content.get("attendees", [])
        )
        title = content.get("title")
        description = content.get("description")
        location = content.get("location")
        organizer_email = content.get("organizer_email")
    else:
        attendees = ()
        title = description = location = organizer_email = None

    return Meeting(
        id=UUID(str(row["id"])),
        tenant_id=UUID(str(row["tenant_id"])),
        jurisdiction=row["jurisdiction"],
        calendar_id=row["calendar_id"],
        google_event_id=row["google_event_id"],
        status=MeetingStatus(row["status"]),
        title=title,
        description=description,
        location=location,
        attendees=attendees,
        organizer_email=organizer_email,
        start_at=row["start_at"],
        end_at=row["end_at"],
        start_raw=row["start_raw"],
        end_raw=row["end_raw"],
        source_updated_at=row["source_updated_at"],
        recurring_event_id=row["recurring_event_id"],
        html_link=row["html_link"],
        content_hash=row["content_hash"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        cancelled_at=row["cancelled_at"],
    )


class PostgresMeetingStore:
    """Adapter implementing MeetingRepository + MeetingReader (D148)."""

    def __init__(
        self,
        *,
        per_tenant_sessionmaker_resolver: _SessionFactoryResolver,
        bound_tenant_id: TenantId,
    ) -> None:
        self._resolve_per_tenant = per_tenant_sessionmaker_resolver
        self._bound_tenant_id = bound_tenant_id

    def _assert_bound(self, tenant_context: TenantContext) -> None:
        if str(tenant_context.tenant_id) != str(self._bound_tenant_id):
            raise ValueError(
                f"TenantContext.tenant_id={tenant_context.tenant_id!r} does "
                f"not match adapter's bound tenant {self._bound_tenant_id!r}; "
                "tenant-isolation defence-in-depth per D24 / D32"
            )

    async def upsert_meeting(
        self, *, tenant_context: TenantContext, meeting: Meeting
    ) -> None:
        self._assert_bound(tenant_context)
        if str(meeting.tenant_id) != str(self._bound_tenant_id):
            raise ValueError(
                f"Meeting.tenant_id={meeting.tenant_id!r} does not match "
                f"adapter's bound tenant {self._bound_tenant_id!r}"
            )
        encrypted = crypto.encrypt_field(
            serialize_meeting_content(meeting),
            _aad_context(meeting.tenant_id),
        )
        values = {
            "id": str(meeting.id),
            "tenant_id": str(meeting.tenant_id),
            "jurisdiction": meeting.jurisdiction,
            "calendar_id": meeting.calendar_id,
            "google_event_id": meeting.google_event_id,
            "status": meeting.status.value,
            "start_at": meeting.start_at,
            "end_at": meeting.end_at,
            "start_raw": meeting.start_raw,
            "end_raw": meeting.end_raw,
            "source_updated_at": meeting.source_updated_at,
            "recurring_event_id": meeting.recurring_event_id,
            "html_link": meeting.html_link,
            "content_hash": meeting.content_hash,
            "enc_wrapped_dek": encrypted.wrapped_dek,
            "enc_dek_wrap_nonce": encrypted.dek_wrap_nonce,
            "enc_ciphertext": encrypted.ciphertext,
            "enc_nonce": encrypted.nonce,
            "enc_key_version": encrypted.key_version,
            "created_at": meeting.created_at,
            "updated_at": meeting.updated_at,
            # A reappearing (previously cancelled) event id un-tombstones.
            "cancelled_at": None,
        }
        stmt = pg_insert(meetings_table).values(**values)
        # Preserve identity and creation time on conflict; refresh everything
        # else from the delta.
        preserved = {
            "id",
            "tenant_id",
            "calendar_id",
            "google_event_id",
            "created_at",
        }
        update_cols = {
            col: stmt.excluded[col]
            for col in values
            if col not in preserved
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "calendar_id", "google_event_id"],
            set_=update_cols,
        )
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(stmt)

    async def tombstone_meeting(
        self,
        *,
        tenant_context: TenantContext,
        calendar_id: str,
        google_event_id: str,
        cancelled_at: datetime,
    ) -> None:
        self._assert_bound(tenant_context)
        # Raw SQL because the embedding column is pgvector-typed and absent
        # from the Core MetaData. Purges content + vector; retains the row.
        # Scoped by calendar_id (D176) so a tombstone in one account never
        # purges a colliding-event-id row in another.
        stmt = sa.text(
            "UPDATE meetings SET "
            "status = 'cancelled', "
            "content_hash = NULL, "
            "enc_wrapped_dek = NULL, "
            "enc_dek_wrap_nonce = NULL, "
            "enc_ciphertext = NULL, "
            "enc_nonce = NULL, "
            "enc_key_version = NULL, "
            "embedding = NULL, "
            "cancelled_at = :cancelled_at, "
            "updated_at = :cancelled_at "
            "WHERE tenant_id = :tenant_id "
            "AND calendar_id = :calendar_id "
            "AND google_event_id = :event_id"
        )
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    stmt,
                    {
                        "cancelled_at": cancelled_at,
                        "tenant_id": str(self._bound_tenant_id),
                        "calendar_id": calendar_id,
                        "event_id": google_event_id,
                    },
                )

    async def set_embedding(
        self,
        *,
        tenant_context: TenantContext,
        calendar_id: str,
        google_event_id: str,
        vector: Sequence[float],
    ) -> None:
        self._assert_bound(tenant_context)
        stmt = sa.text(
            "UPDATE meetings SET embedding = CAST(:vector AS vector) "
            "WHERE tenant_id = :tenant_id "
            "AND calendar_id = :calendar_id "
            "AND google_event_id = :event_id"
        )
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(
                    stmt,
                    {
                        "vector": _format_vector_literal(vector),
                        "tenant_id": str(self._bound_tenant_id),
                        "calendar_id": calendar_id,
                        "event_id": google_event_id,
                    },
                )

    async def get_by_event_id(
        self,
        *,
        tenant_context: TenantContext,
        google_event_id: str,
        calendar_id: str | None = None,
    ) -> Meeting | None:
        self._assert_bound(tenant_context)
        # The write path (sync) passes calendar_id for the exact row of the
        # calendar it is pulling (D176). The read path (the conversation cell)
        # omits it and resolves any calendar's copy of a shared event — fine
        # for a display read, where the duplicate copies are the same event.
        stmt = sa.select(meetings_table).where(
            meetings_table.c.tenant_id == str(self._bound_tenant_id),
            meetings_table.c.google_event_id == google_event_id,
        )
        if calendar_id is not None:
            stmt = stmt.where(meetings_table.c.calendar_id == calendar_id)
        stmt = stmt.order_by(meetings_table.c.created_at.asc())
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            result = await session.execute(stmt)
            row = result.mappings().first()
        if row is None:
            return None
        return _row_to_meeting(dict(row), tenant_id=self._bound_tenant_id)

    async def list_meetings(
        self, *, tenant_context: TenantContext, include_cancelled: bool = False
    ) -> tuple[Meeting, ...]:
        self._assert_bound(tenant_context)
        stmt = sa.select(meetings_table).where(
            meetings_table.c.tenant_id == str(self._bound_tenant_id)
        )
        if not include_cancelled:
            stmt = stmt.where(meetings_table.c.status != "cancelled")
        stmt = stmt.order_by(meetings_table.c.start_at.desc().nullslast())
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            result = await session.execute(stmt)
            rows = result.mappings().all()
        return tuple(
            _row_to_meeting(dict(r), tenant_id=self._bound_tenant_id)
            for r in rows
        )


__all__ = [
    "PostgresMeetingStore",
    "serialize_meeting_content",
    "deserialize_meeting_content",
]
