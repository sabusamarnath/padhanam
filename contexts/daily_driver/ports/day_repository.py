"""Persistence port for the minimal Day concept (D157).

Stores only the user's per-day ordering and done-for-today marks; status
and overdue are computed at render. Tenant + user + day scope every
operation. Ports layer is pure per D16.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol
from uuid import UUID

from contexts.daily_driver.domain.day import DayItemState
from contexts.daily_driver.domain.today_item import ItemKind
from shared_kernel import TenantContext


class DayRepository(Protocol):
    """Persistence port for per-day ordering and done marks."""

    async def get_states(
        self,
        *,
        tenant_context: TenantContext,
        user_id: str,
        day_date: date,
    ) -> tuple[DayItemState, ...]:
        """Return the persisted overrides for one user on one day."""
        ...

    async def set_positions(
        self,
        *,
        tenant_context: TenantContext,
        user_id: str,
        day_date: date,
        ordered_keys: tuple[tuple[ItemKind, UUID], ...],
    ) -> None:
        """Persist the user's explicit ordering as 0-based positions."""
        ...

    async def set_done(
        self,
        *,
        tenant_context: TenantContext,
        user_id: str,
        day_date: date,
        kind: ItemKind,
        item_id: UUID,
        done: bool,
    ) -> None:
        """Set (or clear) the done-for-today mark for one item."""
        ...


__all__ = ["DayRepository"]
