"""TaskSourcePort — the outbound port the pull pipeline depends on (D167).

Exists for hexagonal layering (the application cannot import adapters),
implemented by exactly one adapter this phase (``NangoProxyTaskAdapter``). Not a
vendor-abstraction layer justified by an anticipated second provider — the
two-threshold rule's tell returns *wait* until a second adapter (Trello) is
structurally guaranteed; replaceability is secured by the Connection model and
self-hosting, not by a premature second adapter.

Google Tasks is a two-call shape (the email N+1 precedent): list the task lists,
then list the tasks within each list, paginating each. Read-only — no create/
update/delete method exists, per assess-not-replace (D167).
"""

from __future__ import annotations

from typing import Protocol

from contexts.tasks.domain.connection import Connection
from contexts.tasks.domain.task_source import TaskListPage, TaskPage


class TaskSourcePort(Protocol):
    async def list_task_lists(
        self,
        *,
        connection: Connection,
        page_token: str | None = None,
    ) -> TaskListPage:
        """List the connection's task lists (one page; paginate via the token)."""
        ...

    async def list_tasks(
        self,
        *,
        connection: Connection,
        tasklist_id: str,
        page_token: str | None = None,
        show_completed: bool = True,
        show_hidden: bool = True,
        show_deleted: bool = True,
    ) -> TaskPage:
        """List one page of tasks within a task list. The defaults pull the
        full picture (completed, hidden, and deleted-tombstone tasks) so the
        re-pull is a complete cache refresh; ``show_deleted`` surfaces deletions
        as tombstones."""
        ...


__all__ = ["TaskSourcePort"]
