"""Task — the stored task artefact (D167, D155).

A Task is the persisted, encrypted record minted from a fetched ``SourceTask``
plus tenant context. It is a *mutable cache* keyed on the stable Google task id
(D155 external-source mutable cache): re-pull upserts modified tasks and
tombstones vanished/deleted ones, idempotently. The immutable evidence model is
D155's re-pull-plus-citation-snapshot, not this row.

Content (title + notes — what the user wrote) is field-level encrypted via P3
envelope encryption (D21), mirroring the calendar Meeting and email Email
caches. Structural fields (status, due, completed, tasklist) stay plaintext for
querying. ``to_search_text`` synthesises content into one blob feeding the
content hash used to detect a real content change. Framework-free per D16.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID

from contexts.tasks.domain.task_source import SourceTask


class TaskStatus(StrEnum):
    NEEDS_ACTION = "needsAction"
    COMPLETED = "completed"


@dataclass(frozen=True)
class Task:
    id: UUID
    tenant_id: UUID
    jurisdiction: str
    google_task_id: str
    tasklist_id: str
    tasklist_title: str | None
    status: TaskStatus
    title: str | None
    notes: str | None
    due_at: datetime | None
    completed_at: datetime | None
    parent: str | None
    position: str | None
    source_updated_at: datetime | None
    content_hash: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.jurisdiction or not self.jurisdiction.strip():
            raise ValueError("Task.jurisdiction must be non-empty")
        if not self.google_task_id or not self.google_task_id.strip():
            raise ValueError("Task.google_task_id must be non-empty")
        if not self.tasklist_id or not self.tasklist_id.strip():
            raise ValueError("Task.tasklist_id must be non-empty")
        if self.updated_at < self.created_at:
            raise ValueError("Task.updated_at must be >= created_at")

    @property
    def is_completed(self) -> bool:
        return self.status is TaskStatus.COMPLETED

    def to_search_text(self) -> str:
        return synthesise_task_text(title=self.title, notes=self.notes)


def synthesise_task_text(*, title: str | None, notes: str | None) -> str:
    """Flatten a task's content into one text blob (deterministic field order
    so the content hash is stable across runs)."""
    lines: list[str] = []
    if title:
        lines.append(f"Title: {title}")
    if notes:
        lines.append(f"Notes: {notes}")
    return "\n".join(lines)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_dt(value: str | None) -> datetime | None:
    """Best-effort parse of a Google RFC3339 value to an aware datetime.

    Google Tasks ``due`` is a date carried as an RFC3339 timestamp at midnight
    UTC; ``completed`` is a full RFC3339 timestamp. Naive values anchor to UTC.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def task_from_source(
    source: SourceTask,
    *,
    tasklist_title: str | None,
    tenant_id: UUID,
    jurisdiction: str,
    task_id: UUID,
    now: datetime,
    created_at: datetime | None = None,
) -> Task:
    """Map a live (non-deleted) fetched task to a stored Task.

    Deleted tasks do not flow through here — the pipeline calls the store's
    tombstone path, which purges content. Computes the content hash from the
    synthesised text so the pipeline can detect a real content change.
    """
    try:
        status = TaskStatus(source.status)
    except ValueError:
        status = TaskStatus.NEEDS_ACTION
    text = synthesise_task_text(title=source.title, notes=source.notes)
    return Task(
        id=task_id,
        tenant_id=tenant_id,
        jurisdiction=jurisdiction,
        google_task_id=source.google_task_id,
        tasklist_id=source.tasklist_id,
        tasklist_title=tasklist_title,
        status=status,
        title=source.title,
        notes=source.notes,
        due_at=_parse_dt(source.due),
        completed_at=_parse_dt(source.completed),
        parent=source.parent,
        position=source.position,
        source_updated_at=_parse_dt(source.updated),
        content_hash=_content_hash(text),
        created_at=created_at or now,
        updated_at=now,
    )


__all__ = ["Task", "TaskStatus", "synthesise_task_text", "task_from_source"]
