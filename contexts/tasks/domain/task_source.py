"""Source wire-shape value objects for Google Tasks (D167).

The shapes the ``TaskSourcePort`` returns — the provider's task lists and a
page of tasks — kept separate from the stored ``Task`` (the calendar
``CalendarEvent`` vs ``Meeting`` split). The Nango adapter parses Google's wire
JSON into these; everything Google-specific stays in the adapter.

Reconciled against the current Google Tasks API (2026-06-08): a TaskList has
``id`` + ``title``; a Task has ``id``, ``title``, ``status``
(``needsAction`` / ``completed``), ``notes``, ``due`` (RFC3339 date),
``completed`` (RFC3339 timestamp), ``parent``, ``position``, ``updated``,
``deleted`` (bool), ``hidden`` (bool). The API exposes no recurrence — a
recurring task surfaces as individual instances.

Framework-free per D16.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceTaskList:
    """A Google task list (the container tasks belong to)."""

    tasklist_id: str
    title: str | None


@dataclass(frozen=True)
class SourceTask:
    """A single fetched Google task, before it becomes a stored ``Task``."""

    google_task_id: str
    tasklist_id: str
    status: str  # "needsAction" | "completed" (unknown values default to needsAction)
    title: str | None
    notes: str | None
    due: str | None
    completed: str | None
    parent: str | None
    position: str | None
    updated: str | None
    deleted: bool = False
    hidden: bool = False

    @property
    def is_tombstone(self) -> bool:
        """A deleted task is a tombstone — its content is purged on store."""
        return self.deleted


@dataclass(frozen=True)
class TaskPage:
    """One page of ``tasks.list`` results within a task list."""

    tasks: tuple[SourceTask, ...]
    next_page_token: str | None = None


@dataclass(frozen=True)
class TaskListPage:
    """One page of ``tasklists.list`` results."""

    task_lists: tuple[SourceTaskList, ...]
    next_page_token: str | None = None


__all__ = ["SourceTask", "SourceTaskList", "TaskListPage", "TaskPage"]
