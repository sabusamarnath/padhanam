"""The minimal Day concept — per-day ordering and done-for-today marks (D157).

Only the user's ordering and done marks persist; status and overdue are
computed at render (D157). A ``DayItemState`` is one persisted override
for one (kind, item) on one day: an optional explicit ``position`` and a
``done`` flag. ``item_key`` gives the stable string key the surface and
the store agree on.

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from contexts.daily_driver.domain.today_item import ItemKind


@dataclass(frozen=True)
class DayItemState:
    """A persisted per-day override for one item (D157)."""

    kind: ItemKind
    item_id: UUID
    position: int | None
    done: bool


def item_key(kind: ItemKind, item_id: UUID) -> str:
    """Stable key identifying a today-item across render and store."""
    return f"{kind.value}:{item_id}"


__all__ = ["DayItemState", "item_key"]
