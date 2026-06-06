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
    CALENDAR = "CALENDAR"


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
class CalendarToday:
    """Daily-driver-local projection of a calendar Meeting for today (D159).

    Returned by the ``CalendarEventsReader`` consumer port; the apps-layer
    wiring adapter composes the calendar context's ``MeetingReader``,
    filters to the current day, and maps each Meeting onto this shape (the
    D17 cross-context seam, mirroring ``OpenCase``). ``domain`` is the
    connection's calendar-to-domain tag (work / personal / family); the
    event inherits it (D159).
    """

    meeting_id: UUID
    google_event_id: str
    title: str
    start_at: datetime | None
    end_at: datetime | None
    domain: str


@dataclass(frozen=True)
class TodayItem:
    """One rendered row on the prioritised-today surface (D157, D159).

    ``domain`` (work / personal / family) types the row by domain surface
    (D159, design-language §2): Cases and Commitments are the work domain
    at Phase 2-A; a calendar item inherits its connection's tag. ``start_at``
    carries a calendar item's structured start for time-ordering and the
    drawer's When field (``None`` for Cases and Commitments).
    """

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
    domain: str = "work"
    start_at: datetime | None = None
    # S61 (D162) — the minimal expected-versus-observed loop, surfaced on
    # the row so the drawer renders the gap without a second fetch. Set on
    # Commitments; ``None`` for Cases and calendar items. ``outcome_status``
    # carries the enum *value* (a plain str) for the wire/render layer.
    # ``drop_candidate`` is the recommendation flag (open + quiet past N +
    # not already dropped); the operator acts on it, the platform never
    # auto-drops.
    expected_outcome: str | None = None
    observed_outcome: str | None = None
    outcome_status: str | None = None
    drop_candidate: bool = False


@dataclass(frozen=True)
class TodayView:
    """The ordered prioritised-today list for one user on one day."""

    day_date: date
    items: tuple[TodayItem, ...]


__all__ = [
    "CalendarToday",
    "ItemKind",
    "ItemStatus",
    "OpenCase",
    "TodayItem",
    "TodayView",
]
