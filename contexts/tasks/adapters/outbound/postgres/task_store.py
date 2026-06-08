"""Postgres adapter for the tasks tenant store (D167, D155).

Implements ``TaskRepository`` (write) and ``TaskReader`` (read) against
per-tenant Postgres data planes per D32, with bound-tenant-id defence-in-depth
(D24). Task content (title + notes) is field-level encrypted via P3 envelope
encryption (D21): serialized to JSON, encrypted under a fresh DEK wrapped by the
KEK, stored in the five ``enc_*`` columns; the AAD binds the ciphertext to
``tenant_id`` + the content field. Upsert is idempotent on
``(tenant_id, google_task_id)``; tombstone purges content (the re-pull /
set-diff deletion path). SQLAlchemy 2.0 Core, manual row mapping, no ORM —
mirroring the calendar Meeting and email Email stores.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from padhanam.security import crypto
from shared_kernel import TenantContext, TenantId

from contexts.tasks.adapters.outbound.postgres._tables import tasks as tasks_table
from contexts.tasks.domain.task import Task, TaskStatus

_CONTENT_FIELD = "task_content"


class _SessionFactoryResolver(Protocol):
    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


def _aad_context(tenant_id: object) -> dict[str, str]:
    return {"tenant_id": str(tenant_id), "field": _CONTENT_FIELD}


def serialize_task_content(task: Task) -> bytes:
    payload = {"title": task.title, "notes": task.notes}
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def deserialize_task_content(plaintext: bytes) -> dict[str, Any]:
    return json.loads(plaintext.decode("utf-8"))


def _row_to_task(row: dict[str, Any], *, tenant_id: object) -> Task:
    if row["enc_ciphertext"] is not None:
        field = crypto.EncryptedField(
            wrapped_dek=bytes(row["enc_wrapped_dek"]),
            dek_wrap_nonce=bytes(row["enc_dek_wrap_nonce"]),
            ciphertext=bytes(row["enc_ciphertext"]),
            nonce=bytes(row["enc_nonce"]),
            key_version=int(row["enc_key_version"]),
        )
        content = deserialize_task_content(
            crypto.decrypt_field(field, _aad_context(tenant_id))
        )
        title = content.get("title")
        notes = content.get("notes")
    else:
        title = notes = None

    return Task(
        id=UUID(str(row["id"])),
        tenant_id=UUID(str(row["tenant_id"])),
        jurisdiction=row["jurisdiction"],
        google_task_id=row["google_task_id"],
        tasklist_id=row["tasklist_id"],
        tasklist_title=row["tasklist_title"],
        status=TaskStatus(row["status"]),
        title=title,
        notes=notes,
        due_at=row["due_at"],
        completed_at=row["completed_at"],
        parent=row["parent"],
        position=row["position"],
        source_updated_at=row["source_updated_at"],
        content_hash=row["content_hash"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
    )


class PostgresTaskStore:
    """Adapter implementing TaskRepository + TaskReader (D167)."""

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

    async def upsert_task(
        self, *, tenant_context: TenantContext, task: Task
    ) -> None:
        self._assert_bound(tenant_context)
        if str(task.tenant_id) != str(self._bound_tenant_id):
            raise ValueError(
                f"Task.tenant_id={task.tenant_id!r} does not match adapter's "
                f"bound tenant {self._bound_tenant_id!r}"
            )
        encrypted = crypto.encrypt_field(
            serialize_task_content(task), _aad_context(task.tenant_id)
        )
        values = {
            "id": str(task.id),
            "tenant_id": str(task.tenant_id),
            "jurisdiction": task.jurisdiction,
            "google_task_id": task.google_task_id,
            "tasklist_id": task.tasklist_id,
            "tasklist_title": task.tasklist_title,
            "status": task.status.value,
            "due_at": task.due_at,
            "completed_at": task.completed_at,
            "parent": task.parent,
            "position": task.position,
            "source_updated_at": task.source_updated_at,
            "content_hash": task.content_hash,
            "enc_wrapped_dek": encrypted.wrapped_dek,
            "enc_dek_wrap_nonce": encrypted.dek_wrap_nonce,
            "enc_ciphertext": encrypted.ciphertext,
            "enc_nonce": encrypted.nonce,
            "enc_key_version": encrypted.key_version,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            # A reappearing (previously deleted) task id un-tombstones.
            "deleted_at": None,
        }
        stmt = pg_insert(tasks_table).values(**values)
        preserved = {"id", "tenant_id", "google_task_id", "created_at"}
        update_cols = {
            col: stmt.excluded[col] for col in values if col not in preserved
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "google_task_id"],
            set_=update_cols,
        )
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(stmt)

    async def tombstone_task(
        self,
        *,
        tenant_context: TenantContext,
        google_task_id: str,
        deleted_at: datetime,
    ) -> None:
        self._assert_bound(tenant_context)
        stmt = (
            sa.update(tasks_table)
            .where(
                tasks_table.c.tenant_id == str(self._bound_tenant_id),
                tasks_table.c.google_task_id == google_task_id,
            )
            .values(
                content_hash=None,
                enc_wrapped_dek=None,
                enc_dek_wrap_nonce=None,
                enc_ciphertext=None,
                enc_nonce=None,
                enc_key_version=None,
                deleted_at=deleted_at,
                updated_at=deleted_at,
            )
        )
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            async with session.begin():
                await session.execute(stmt)

    async def get_by_google_id(
        self, *, tenant_context: TenantContext, google_task_id: str
    ) -> Task | None:
        self._assert_bound(tenant_context)
        stmt = sa.select(tasks_table).where(
            tasks_table.c.tenant_id == str(self._bound_tenant_id),
            tasks_table.c.google_task_id == google_task_id,
        )
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            row = (await session.execute(stmt)).mappings().first()
        if row is None:
            return None
        return _row_to_task(dict(row), tenant_id=self._bound_tenant_id)

    async def list_google_ids(
        self, *, tenant_context: TenantContext
    ) -> tuple[str, ...]:
        self._assert_bound(tenant_context)
        stmt = sa.select(tasks_table.c.google_task_id).where(
            tasks_table.c.tenant_id == str(self._bound_tenant_id),
            tasks_table.c.deleted_at.is_(None),
        )
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return tuple(rows)

    async def list_tasks(
        self, *, tenant_context: TenantContext, include_completed: bool = True
    ) -> tuple[Task, ...]:
        self._assert_bound(tenant_context)
        stmt = sa.select(tasks_table).where(
            tasks_table.c.tenant_id == str(self._bound_tenant_id),
            tasks_table.c.deleted_at.is_(None),
        )
        if not include_completed:
            stmt = stmt.where(tasks_table.c.status != TaskStatus.COMPLETED.value)
        stmt = stmt.order_by(tasks_table.c.due_at.asc().nullslast())
        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            rows = (await session.execute(stmt)).mappings().all()
        return tuple(
            _row_to_task(dict(r), tenant_id=self._bound_tenant_id) for r in rows
        )


__all__ = [
    "PostgresTaskStore",
    "deserialize_task_content",
    "serialize_task_content",
]
