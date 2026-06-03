"""Postgres adapters for the email substrate (D151, D21, D24).

PostgresEmailStore (EmailRepository + EmailReader) and
PostgresEmailChunkStore (EmailChunkRepository), both with bound-tenant-id
defence-in-depth (D24). Sensitive content (subject/body/addresses/snippet
on emails; chunk text on email_chunks) is P3 envelope-encrypted via
``padhanam/security/crypto.py`` (D21), AAD-bound to tenant_id + field, so
nothing readable persists at rest. Per-chunk ``embedding vector(768)`` is
written in raw SQL (the column is outside the Core MetaData). Mirrors the
calendar meeting_store; SQLAlchemy 2.0 Core, no ORM.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Protocol, Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from padhanam.security import crypto
from shared_kernel import TenantContext, TenantId

from contexts.email.adapters.outbound.postgres._tables import (
    email_chunks as email_chunks_table,
    emails as emails_table,
)
from contexts.email.domain.email import Email, serialize_email_content
from contexts.email.domain.email_chunk import EmailChunk

_CONTENT_FIELD = "email_content"
_CHUNK_FIELD = "email_chunk"


class _SessionFactoryResolver(Protocol):
    async def __call__(self, tenant_id: TenantId) -> async_sessionmaker[AsyncSession]: ...


def _aad(tenant_id: object, field: str) -> dict[str, str]:
    return {"tenant_id": str(tenant_id), "field": field}


def _deserialize(plaintext: bytes) -> dict[str, Any]:
    return json.loads(plaintext.decode("utf-8"))


def _format_vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"


def _row_to_email(row: dict[str, Any], *, tenant_id: object) -> Email:
    if row["enc_ciphertext"] is not None:
        field = crypto.EncryptedField(
            wrapped_dek=bytes(row["enc_wrapped_dek"]),
            dek_wrap_nonce=bytes(row["enc_dek_wrap_nonce"]),
            ciphertext=bytes(row["enc_ciphertext"]),
            nonce=bytes(row["enc_nonce"]),
            key_version=int(row["enc_key_version"]),
        )
        content = _deserialize(crypto.decrypt_field(field, _aad(tenant_id, _CONTENT_FIELD)))
        subject = content.get("subject")
        body = content.get("body")
        snippet = content.get("snippet")
        from_address = content.get("from_address")
        to_addresses = tuple(content.get("to_addresses", []))
        cc_addresses = tuple(content.get("cc_addresses", []))
    else:
        subject = body = snippet = from_address = None
        to_addresses = cc_addresses = ()
    return Email(
        id=UUID(str(row["id"])),
        tenant_id=UUID(str(row["tenant_id"])),
        jurisdiction=row["jurisdiction"],
        message_id=row["message_id"],
        thread_id=row["thread_id"],
        from_address=from_address,
        to_addresses=to_addresses,
        cc_addresses=cc_addresses,
        subject=subject,
        body=body,
        snippet=snippet,
        received_at=row["received_at"],
        labels=tuple(row["labels"] or ()),
        history_id=row["history_id"],
        content_hash=row["content_hash"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
    )


class PostgresEmailStore:
    """EmailRepository + EmailReader adapter (D151)."""

    def __init__(
        self, *, per_tenant_sessionmaker_resolver: _SessionFactoryResolver, bound_tenant_id: TenantId
    ) -> None:
        self._resolve = per_tenant_sessionmaker_resolver
        self._bound = bound_tenant_id

    def _assert_bound(self, tc: TenantContext) -> None:
        if str(tc.tenant_id) != str(self._bound):
            raise ValueError(
                f"TenantContext.tenant_id={tc.tenant_id!r} does not match bound "
                f"tenant {self._bound!r}; tenant-isolation defence-in-depth (D24/D32)"
            )

    async def upsert_email(self, *, tenant_context: TenantContext, email: Email) -> None:
        self._assert_bound(tenant_context)
        enc = crypto.encrypt_field(
            serialize_email_content(email), _aad(email.tenant_id, _CONTENT_FIELD)
        )
        values = {
            "id": str(email.id),
            "tenant_id": str(email.tenant_id),
            "jurisdiction": email.jurisdiction,
            "message_id": email.message_id,
            "thread_id": email.thread_id,
            "received_at": email.received_at,
            "labels": list(email.labels),
            "history_id": email.history_id,
            "content_hash": email.content_hash,
            "enc_wrapped_dek": enc.wrapped_dek,
            "enc_dek_wrap_nonce": enc.dek_wrap_nonce,
            "enc_ciphertext": enc.ciphertext,
            "enc_nonce": enc.nonce,
            "enc_key_version": enc.key_version,
            "created_at": email.created_at,
            "updated_at": email.updated_at,
            "deleted_at": None,
        }
        stmt = pg_insert(emails_table).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "message_id"],
            set_={
                "thread_id": stmt.excluded.thread_id,
                "received_at": stmt.excluded.received_at,
                "labels": stmt.excluded.labels,
                "history_id": stmt.excluded.history_id,
                "content_hash": stmt.excluded.content_hash,
                "enc_wrapped_dek": stmt.excluded.enc_wrapped_dek,
                "enc_dek_wrap_nonce": stmt.excluded.enc_dek_wrap_nonce,
                "enc_ciphertext": stmt.excluded.enc_ciphertext,
                "enc_nonce": stmt.excluded.enc_nonce,
                "enc_key_version": stmt.excluded.enc_key_version,
                "updated_at": stmt.excluded.updated_at,
                # A re-appearing message id un-tombstones.
                "deleted_at": None,
            },
        )
        sm = await self._resolve(self._bound)
        async with sm() as s:
            async with s.begin():
                await s.execute(stmt)

    async def tombstone_email(
        self, *, tenant_context: TenantContext, message_id: str, deleted_at: datetime
    ) -> None:
        self._assert_bound(tenant_context)
        stmt = (
            sa.update(emails_table)
            .where(
                emails_table.c.tenant_id == str(self._bound),
                emails_table.c.message_id == message_id,
            )
            .values(
                deleted_at=deleted_at,
                updated_at=deleted_at,
                content_hash=None,
                enc_wrapped_dek=None,
                enc_dek_wrap_nonce=None,
                enc_ciphertext=None,
                enc_nonce=None,
                enc_key_version=None,
            )
        )
        sm = await self._resolve(self._bound)
        async with sm() as s:
            async with s.begin():
                await s.execute(stmt)
                await s.execute(
                    sa.delete(email_chunks_table).where(
                        email_chunks_table.c.tenant_id == str(self._bound),
                        email_chunks_table.c.message_id == message_id,
                    )
                )

    async def get_by_message_id(
        self, *, tenant_context: TenantContext, message_id: str
    ) -> Email | None:
        self._assert_bound(tenant_context)
        stmt = sa.select(emails_table).where(
            emails_table.c.tenant_id == str(self._bound),
            emails_table.c.message_id == message_id,
        )
        sm = await self._resolve(self._bound)
        async with sm() as s:
            row = (await s.execute(stmt)).mappings().first()
        return _row_to_email(dict(row), tenant_id=self._bound) if row else None

    async def list_emails(
        self, *, tenant_context: TenantContext, include_deleted: bool = False
    ) -> tuple[Email, ...]:
        self._assert_bound(tenant_context)
        conds = [emails_table.c.tenant_id == str(self._bound)]
        if not include_deleted:
            conds.append(emails_table.c.deleted_at.is_(None))
        stmt = sa.select(emails_table).where(*conds).order_by(
            emails_table.c.received_at.desc().nullslast()
        )
        sm = await self._resolve(self._bound)
        async with sm() as s:
            rows = (await s.execute(stmt)).mappings().all()
        return tuple(_row_to_email(dict(r), tenant_id=self._bound) for r in rows)

    async def list_live_message_ids_in_window(
        self, *, tenant_context: TenantContext, window_start: datetime
    ) -> frozenset[str]:
        self._assert_bound(tenant_context)
        stmt = sa.select(emails_table.c.message_id).where(
            emails_table.c.tenant_id == str(self._bound),
            emails_table.c.deleted_at.is_(None),
            emails_table.c.received_at >= window_start,
        )
        sm = await self._resolve(self._bound)
        async with sm() as s:
            rows = (await s.execute(stmt)).scalars().all()
        return frozenset(str(r) for r in rows)


class PostgresEmailChunkStore:
    """EmailChunkRepository adapter — the email-local chunk store (D151)."""

    def __init__(
        self, *, per_tenant_sessionmaker_resolver: _SessionFactoryResolver, bound_tenant_id: TenantId
    ) -> None:
        self._resolve = per_tenant_sessionmaker_resolver
        self._bound = bound_tenant_id

    def _assert_bound(self, tc: TenantContext) -> None:
        if str(tc.tenant_id) != str(self._bound):
            raise ValueError("email chunk store bound-tenant mismatch (D24/D32)")

    async def replace_chunks(
        self,
        *,
        tenant_context: TenantContext,
        email_id: UUID,
        message_id: str,
        chunks: Sequence[tuple[EmailChunk, Sequence[float]]],
    ) -> None:
        self._assert_bound(tenant_context)
        sm = await self._resolve(self._bound)
        async with sm() as s:
            async with s.begin():
                await s.execute(
                    sa.delete(email_chunks_table).where(
                        email_chunks_table.c.tenant_id == str(self._bound),
                        email_chunks_table.c.message_id == message_id,
                    )
                )
                for chunk, vector in chunks:
                    enc = crypto.encrypt_field(
                        chunk.content.encode("utf-8"),
                        _aad(tenant_context.tenant_id, _CHUNK_FIELD),
                    )
                    await s.execute(
                        sa.text(
                            "INSERT INTO email_chunks (id, tenant_id, jurisdiction, "
                            "email_id, message_id, chunk_index, enc_wrapped_dek, "
                            "enc_dek_wrap_nonce, enc_ciphertext, enc_nonce, "
                            "enc_key_version, embedding) VALUES (:id, :tid, :juris, "
                            ":eid, :mid, :idx, :wdek, :dnonce, :ct, :nonce, :kv, "
                            "CAST(:vec AS vector))"
                        ),
                        {
                            "id": str(chunk.id),
                            "tid": str(self._bound),
                            "juris": tenant_context.jurisdiction,
                            "eid": str(email_id),
                            "mid": message_id,
                            "idx": chunk.chunk_index,
                            "wdek": enc.wrapped_dek,
                            "dnonce": enc.dek_wrap_nonce,
                            "ct": enc.ciphertext,
                            "nonce": enc.nonce,
                            "kv": enc.key_version,
                            "vec": _format_vector_literal(vector),
                        },
                    )

    async def delete_chunks_for_message(
        self, *, tenant_context: TenantContext, message_id: str
    ) -> None:
        self._assert_bound(tenant_context)
        sm = await self._resolve(self._bound)
        async with sm() as s:
            async with s.begin():
                await s.execute(
                    sa.delete(email_chunks_table).where(
                        email_chunks_table.c.tenant_id == str(self._bound),
                        email_chunks_table.c.message_id == message_id,
                    )
                )


__all__ = ["PostgresEmailChunkStore", "PostgresEmailStore"]
