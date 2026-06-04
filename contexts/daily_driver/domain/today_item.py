"""Today-item value objects — the rendered units of the prioritised list (D157).

A ``TodayItem`` is one row on the prioritised-today surface: an OPEN
Case or a Commitment, carrying its computed ``status`` (never
persisted), the cell it opens into, and the artefact it references. The
``OpenCase`` value object is the daily-driver-local projection of a
portfolio Case the ``OpenCasesReader`` consumer port returns.

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from uuid import UUID


class ItemKind(str, Enum):
    """The kind of a today-item."""

    CASE = "CASE"
    COMMITMENT = "COMMITMENT"


class ItemStatus(str, Enum):
    """Computed status of a today-item (D157 — computed at render, never stored).

    ``NEEDS_YOU`` an OPEN Case awaiting the user; ``ON_TRACK`` a
    Commitment within its interval; ``BEHIND`` a Commitment past its
    interval (the active-surfacing differentiator); ``DONE`` the
    per-day done-for-today overlay.
    """

    NEEDS_YOU = "NEEDS_YOU"
    ON_TRACK = "ON_TRACK"
    BEHIND = "BEHIND"
    DONE = "DONE"


@dataclass(frozen=True)
class OpenCase:
    """Daily-driver-local projection of an OPEN portfolio Case.

    Returned by the ``OpenCasesReader`` consumer port; the apps-layer
    wiring adapter maps the portfolio ``Case`` onto this shape (the D17
    cross-context seam).
    """

    case_id: UUID
    title: str
    created_at: datetime


@dataclass(frozen=True)
class TodayItem:
    """One rendered row on the prioritised-today surface (D157)."""

    kind: ItemKind
    item_id: UUID
    title: str
    status: ItemStatus
    target_cell: str
    artefact_type: str
    detail: str
    position: int | None
    done: bool
    overdue_by_days: int | None = None


@dataclass(frozen=True)
class TodayView:
    """The ordered prioritised-today list for one user on one day."""

    day_date: date
    items: tuple[TodayItem, ...]


__all__ = [
    "ItemKind",
    "ItemStatus",
    "OpenCase",
    "TodayItem",
    "TodayView",
]
