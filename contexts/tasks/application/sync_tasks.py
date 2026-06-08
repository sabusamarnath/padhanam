"""sync_tasks — the trigger-agnostic pull-store-sync pipeline (D167, D155).

A function, not a Protocol (the calendar/email precedent): it takes its trigger
context as a plain parameter with one caller today (the poll). Google Tasks is a
two-call shape — list the task lists, then drain each list's tasks — so the pull
is an N+1 over lists (the email N+1 precedent). It stores each task keyed on the
Google task id (upsert modified, tombstone deleted), then **set-diffs** the
stored ids against the ids just seen and tombstones any that vanished from the
source — so the re-pull is a complete, idempotent cache refresh (D155).

Read-only: nothing here writes to Google. Emits no audit events — per D155 the
``tasks`` store is an external-source mutable cache, excluded from the
audit-trail-as-source-of-truth principle; its upsert/tombstone churn is not
chained.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from contexts.tasks.domain.errors import NoSuchConnectionError
from contexts.tasks.domain.sync_trigger import TaskSyncTrigger
from contexts.tasks.domain.task import task_from_source
from contexts.tasks.domain.task_source import SourceTask
from contexts.tasks.ports.connection_repository import ConnectionRepository
from contexts.tasks.ports.task_repository import TaskReader, TaskRepository
from contexts.tasks.ports.task_source_port import TaskSourcePort
from shared_kernel.tenant_context import TenantContext

_MAX_PAGES = 100


@dataclass(frozen=True)
class TaskSyncResult:
    fetched: int
    upserted: int
    tombstoned: int
    changed_task_ids: tuple[str, ...]


async def sync_tasks(
    *,
    tenant_context: TenantContext,
    connection_id: UUID,
    trigger: TaskSyncTrigger,
    task_source: TaskSourcePort,
    connections: ConnectionRepository,
    tasks: TaskRepository,
    task_reader: TaskReader,
    now: datetime | None = None,
) -> TaskSyncResult:
    """Pull, store, and set-diff one task connection (D167).

    ``trigger`` is the trigger-agnostic seam (a poll today; a future webhook
    would drive the same function). The pull is a full re-pull every call: it
    drains every task list and every page, upserts live tasks, tombstones
    deleted ones, and finally tombstones any stored task whose id did not appear
    in the pull (a deletion the source no longer returns at all).
    """
    del trigger  # recorded by the caller; no branch on it today
    now = now or datetime.now(timezone.utc)

    connection = await connections.get_connection(
        tenant_context=tenant_context, connection_id=connection_id
    )
    if connection is None:
        raise NoSuchConnectionError(str(connection_id))

    sources = await _drain_all(task_source, connection)

    seen_ids: set[str] = set()
    upserted = 0
    tombstoned = 0
    changed: list[str] = []
    for source, tasklist_title in sources:
        seen_ids.add(source.google_task_id)
        if source.is_tombstone:
            await tasks.tombstone_task(
                tenant_context=tenant_context,
                google_task_id=source.google_task_id,
                deleted_at=now,
            )
            tombstoned += 1
            continue
        existing = await task_reader.get_by_google_id(
            tenant_context=tenant_context,
            google_task_id=source.google_task_id,
        )
        task = task_from_source(
            source,
            tasklist_title=tasklist_title,
            tenant_id=UUID(tenant_context.tenant_id),
            jurisdiction=tenant_context.jurisdiction,
            task_id=existing.id if existing is not None else uuid4(),
            now=now,
            created_at=existing.created_at if existing is not None else None,
        )
        await tasks.upsert_task(tenant_context=tenant_context, task=task)
        upserted += 1
        if existing is None or existing.content_hash != task.content_hash:
            changed.append(source.google_task_id)

    # Set-diff deletion: a stored task whose id did not appear in the pull has
    # vanished from the source (deleted beyond the showDeleted window) — tombstone it.
    stored_ids = await task_reader.list_google_ids(tenant_context=tenant_context)
    for gid in stored_ids:
        if gid not in seen_ids:
            await tasks.tombstone_task(
                tenant_context=tenant_context,
                google_task_id=gid,
                deleted_at=now,
            )
            tombstoned += 1

    return TaskSyncResult(
        fetched=len(sources),
        upserted=upserted,
        tombstoned=tombstoned,
        changed_task_ids=tuple(changed),
    )


async def _drain_all(
    task_source: TaskSourcePort, connection
) -> list[tuple[SourceTask, str | None]]:
    """Drain every task across every task list, pairing each with its list
    title. Two-call N+1: list lists, then drain each list's task pages."""
    collected: list[tuple[SourceTask, str | None]] = []
    list_page_token: str | None = None
    for _ in range(_MAX_PAGES):
        list_page = await task_source.list_task_lists(
            connection=connection, page_token=list_page_token
        )
        for tasklist in list_page.task_lists:
            task_page_token: str | None = None
            for _ in range(_MAX_PAGES):
                page = await task_source.list_tasks(
                    connection=connection,
                    tasklist_id=tasklist.tasklist_id,
                    page_token=task_page_token,
                )
                collected.extend((t, tasklist.title) for t in page.tasks)
                if not page.next_page_token:
                    break
                task_page_token = page.next_page_token
        if not list_page.next_page_token:
            break
        list_page_token = list_page.next_page_token
    return collected


__all__ = ["TaskSyncResult", "sync_tasks"]
