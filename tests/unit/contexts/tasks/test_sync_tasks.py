"""Unit tests for sync_tasks (D167): drain, upsert, tombstone, set-diff, idempotency."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from contexts.tasks.application.sync_tasks import sync_tasks
from contexts.tasks.domain.connection import Connection
from contexts.tasks.domain.errors import NoSuchConnectionError
from contexts.tasks.domain.sync_trigger import TaskSyncTrigger
from contexts.tasks.domain.task import Task
from contexts.tasks.domain.task_source import (
    SourceTask,
    SourceTaskList,
    TaskListPage,
    TaskPage,
)

_NOW = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
_TENANT_ID = "00000000-0000-4000-8000-00000000d001"


def _tc():
    from shared_kernel import TenantContext

    return TenantContext(
        tenant_id=_TENANT_ID, jurisdiction="eu-west", cost_attribution_id=_TENANT_ID
    )


def _conn() -> Connection:
    return Connection(
        id=uuid4(),
        tenant_id=UUID(_TENANT_ID),
        jurisdiction="eu-west",
        provider="google_tasks",
        provider_config_key="google-tasks",
        provider_connection_ref="ref",
        created_at=_NOW,
        updated_at=_NOW,
    )


class _FakeConnections:
    def __init__(self, conn: Connection | None) -> None:
        self._conn = conn

    async def get_connection(self, *, tenant_context, connection_id):
        return self._conn

    async def save_connection(self, *, tenant_context, connection):
        self._conn = connection


class _FakeSource:
    """Returns one list with the supplied tasks (single page)."""

    def __init__(self, tasks: list[SourceTask], *, list_title="My Tasks") -> None:
        self._tasks = tasks
        self._list_title = list_title

    async def list_task_lists(self, *, connection, page_token=None):
        return TaskListPage(
            task_lists=(SourceTaskList(tasklist_id="L1", title=self._list_title),)
        )

    async def list_tasks(self, *, connection, tasklist_id, page_token=None, **kw):
        return TaskPage(tasks=tuple(self._tasks))


class _FakeStore:
    """In-memory TaskRepository + TaskReader."""

    def __init__(self) -> None:
        self.by_gid: dict[str, Task] = {}

    async def upsert_task(self, *, tenant_context, task):
        self.by_gid[task.google_task_id] = task

    async def tombstone_task(self, *, tenant_context, google_task_id, deleted_at):
        t = self.by_gid.get(google_task_id)
        if t is not None:
            from dataclasses import replace

            self.by_gid[google_task_id] = replace(
                t, deleted_at=deleted_at, content_hash=None
            )

    async def get_by_google_id(self, *, tenant_context, google_task_id):
        t = self.by_gid.get(google_task_id)
        return t if (t is not None and t.deleted_at is None) else None

    async def list_google_ids(self, *, tenant_context):
        return tuple(g for g, t in self.by_gid.items() if t.deleted_at is None)

    async def list_tasks(self, *, tenant_context, include_completed=True):
        return tuple(t for t in self.by_gid.values() if t.deleted_at is None)


def _src(gid: str, **kw) -> SourceTask:
    base = dict(
        google_task_id=gid, tasklist_id="L1", status="needsAction",
        title=f"task {gid}", notes=None, due=None, completed=None,
        parent=None, position=None, updated=None, deleted=False, hidden=False,
    )
    base.update(kw)
    return SourceTask(**base)


def _run(source, store, connections):
    return asyncio.run(
        sync_tasks(
            tenant_context=_tc(),
            connection_id=uuid4(),
            trigger=TaskSyncTrigger.POLL,
            task_source=source,
            connections=connections,
            tasks=store,
            task_reader=store,
            now=_NOW,
        )
    )


def test_pull_upserts_live_tasks() -> None:
    store = _FakeStore()
    res = _run(_FakeSource([_src("a"), _src("b")]), store, _FakeConnections(_conn()))
    assert res.upserted == 2
    assert res.fetched == 2
    assert set(store.by_gid) == {"a", "b"}
    assert store.by_gid["a"].tasklist_title == "My Tasks"


def test_deleted_task_is_tombstoned() -> None:
    store = _FakeStore()
    res = _run(
        _FakeSource([_src("a"), _src("b", deleted=True)]),
        store,
        _FakeConnections(_conn()),
    )
    assert res.upserted == 1
    assert res.tombstoned == 1


def test_vanished_task_set_diff_tombstoned_on_repull() -> None:
    store = _FakeStore()
    conns = _FakeConnections(_conn())
    _run(_FakeSource([_src("a"), _src("b")]), store, conns)
    # Second pull no longer returns "b" at all → set-diff tombstones it.
    res = _run(_FakeSource([_src("a")]), store, conns)
    assert res.tombstoned == 1
    assert store.by_gid["b"].deleted_at is not None
    assert store.by_gid["a"].deleted_at is None


def test_repull_is_idempotent() -> None:
    store = _FakeStore()
    conns = _FakeConnections(_conn())
    _run(_FakeSource([_src("a"), _src("b")]), store, conns)
    id_a = store.by_gid["a"].id
    res = _run(_FakeSource([_src("a"), _src("b")]), store, conns)
    # Same set re-pulled: still two live rows, identity preserved, none tombstoned.
    assert res.tombstoned == 0
    assert store.by_gid["a"].id == id_a
    assert {g for g, t in store.by_gid.items() if t.deleted_at is None} == {"a", "b"}


def test_missing_connection_raises() -> None:
    with pytest.raises(NoSuchConnectionError):
        _run(_FakeSource([]), _FakeStore(), _FakeConnections(None))
