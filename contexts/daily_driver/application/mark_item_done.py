"""mark_item_done use case — the done-for-today overlay (D157).

Sets or clears the per-day done mark for one item. For a Commitment the
surface also logs a completion (which clears the "behind on this"
signal); that is a distinct call to ``log_commitment_completion`` — this
use case only owns the per-day Day-concept overlay, so a Case can be
marked done-for-today without mutating any canonical state.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from contexts.daily_driver.domain.today_item import ItemKind
from contexts.daily_driver.ports.day_repository import DayRepository
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_TODAY_WRITE,
    requires_authorisation,
)


@requires_authorisation(DAILY_DRIVER_TODAY_WRITE)
async def mark_item_done(
    *,
    day_repository: DayRepository,
    actor: ActorContext,
    kind: ItemKind,
    item_id: UUID,
    done: bool,
    now: datetime,
) -> None:
    """Set the done-for-today mark for one item on the current UTC day.

    ``now`` is the day's clock, threaded from the caller through the seam
    (S75/S76, required so it cannot be minted internally): the done mark
    keys on ``now.date()``, deterministic in tests, the production caller
    passing the real wall clock.
    """
    day_date = now.date()
    await day_repository.set_done(
        tenant_context=actor.tenant_context,
        user_id=actor.actor_id,
        day_date=day_date,
        kind=kind,
        item_id=item_id,
        done=done,
    )


__all__ = ["mark_item_done"]
