"""TaskRepository (write) + TaskReader (read) ports for the tasks cache (D167).

The re-pullable cache surface (D155). ``upsert_task`` is idempotent on
``(tenant_id, google_task_id)``; ``tombstone_task`` purges content and marks the
row deleted (a vanished or deleted task); ``list_tasks`` and ``list_google_ids``
feed the sync pipeline's set-diff and the daily-driver read. Read-only toward
the provider — nothing here writes back to Google.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from contexts.tasks.domain.task import Task
from shared_kernel import TenantContext


class TaskRepository(Protocol):
    async def upsert_task(
        self, *, tenant_context: TenantContext, task: Task
    ) -> None:
        ...

    async def tombstone_task(
        self,
        *,
        tenant_context: TenantContext,
        google_task_id: str,
        deleted_at: datetime,
    ) -> None:
        ...


class TaskReader(Protocol):
    async def get_by_google_id(
        self, *, tenant_context: TenantContext, google_task_id: str
    ) -> Task | None:
        ...

    async def list_google_ids(
        self, *, tenant_context: TenantContext
    ) -> tuple[str, ...]:
        """Every non-deleted task's google id — the set-diff input for
        tombstoning tasks that vanished from the source on re-pull."""
        ...

    async def list_tasks(
        self, *, tenant_context: TenantContext, include_completed: bool = True
    ) -> tuple[Task, ...]:
        ...


__all__ = ["TaskReader", "TaskRepository"]
