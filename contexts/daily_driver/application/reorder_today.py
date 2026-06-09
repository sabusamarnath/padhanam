"""set_today_order use case — persist the user's ordering (D157).

The minimal Day concept: the user's explicit ordering persists as 0-based
positions for the current UTC day. Status and overdue stay computed at
render.
"""

from __future__ import annotations

from datetime import datetime

from contexts.daily_driver.domain.today_item import ItemKind
from contexts.daily_driver.ports.day_repository import DayRepository
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_TODAY_WRITE,
    requires_authorisation,
)
from uuid import UUID


@requires_authorisation(DAILY_DRIVER_TODAY_WRITE)
async def set_today_order(
    *,
    day_repository: DayRepository,
    actor: ActorContext,
    ordered_keys: tuple[tuple[ItemKind, UUID], ...],
    now: datetime,
) -> None:
    """Persist the user's ordering for the current UTC day.

    ``now`` is the day's clock, threaded from the caller through the seam
    (S75/S76, required so it cannot be minted internally): the ordering keys
    on ``now.date()``, deterministic in tests, the production caller passing
    the real wall clock.
    """
    day_date = now.date()
    await day_repository.set_positions(
        tenant_context=actor.tenant_context,
        user_id=actor.actor_id,
        day_date=day_date,
        ordered_keys=ordered_keys,
    )


__all__ = ["set_today_order"]
