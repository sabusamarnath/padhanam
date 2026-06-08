"""Unit tests for the tasks domain (D167): task_from_source mapping + invariants."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contexts.tasks.domain.task import Task, TaskStatus, task_from_source
from contexts.tasks.domain.task_source import SourceTask

_NOW = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
_TENANT = uuid4()


def _source(**overrides) -> SourceTask:
    base = dict(
        google_task_id="t1",
        tasklist_id="list-1",
        status="needsAction",
        title="Apply to roles",
        notes="shortlist five",
        due="2026-06-10T00:00:00.000Z",
        completed=None,
        parent=None,
        position="00000000000000000001",
        updated="2026-06-08T09:00:00.000Z",
        deleted=False,
        hidden=False,
    )
    base.update(overrides)
    return SourceTask(**base)


def test_task_from_source_maps_fields_and_parses_dates() -> None:
    task = task_from_source(
        _source(),
        tasklist_title="My Tasks",
        tenant_id=_TENANT,
        jurisdiction="eu-west",
        task_id=uuid4(),
        now=_NOW,
    )
    assert task.google_task_id == "t1"
    assert task.tasklist_id == "list-1"
    assert task.tasklist_title == "My Tasks"
    assert task.status is TaskStatus.NEEDS_ACTION
    assert task.title == "Apply to roles"
    assert task.due_at == datetime(2026, 6, 10, 0, 0, tzinfo=timezone.utc)
    assert task.completed_at is None
    assert task.content_hash is not None


def test_completed_task_carries_completed_at() -> None:
    task = task_from_source(
        _source(status="completed", completed="2026-06-07T12:00:00.000Z"),
        tasklist_title="Work",
        tenant_id=_TENANT,
        jurisdiction="eu-west",
        task_id=uuid4(),
        now=_NOW,
    )
    assert task.status is TaskStatus.COMPLETED
    assert task.is_completed is True
    assert task.completed_at == datetime(2026, 6, 7, 12, 0, tzinfo=timezone.utc)


def test_unknown_status_defaults_to_needs_action() -> None:
    task = task_from_source(
        _source(status="weird"),
        tasklist_title=None,
        tenant_id=_TENANT,
        jurisdiction="eu-west",
        task_id=uuid4(),
        now=_NOW,
    )
    assert task.status is TaskStatus.NEEDS_ACTION


def test_content_hash_changes_with_content() -> None:
    a = task_from_source(
        _source(title="A"), tasklist_title=None, tenant_id=_TENANT,
        jurisdiction="eu-west", task_id=uuid4(), now=_NOW,
    )
    b = task_from_source(
        _source(title="B"), tasklist_title=None, tenant_id=_TENANT,
        jurisdiction="eu-west", task_id=uuid4(), now=_NOW,
    )
    assert a.content_hash != b.content_hash


def test_blank_google_id_rejected() -> None:
    with pytest.raises(ValueError):
        Task(
            id=uuid4(), tenant_id=_TENANT, jurisdiction="eu-west",
            google_task_id="  ", tasklist_id="l", tasklist_title=None,
            status=TaskStatus.NEEDS_ACTION, title=None, notes=None,
            due_at=None, completed_at=None, parent=None, position=None,
            source_updated_at=None, content_hash=None,
            created_at=_NOW, updated_at=_NOW,
        )
