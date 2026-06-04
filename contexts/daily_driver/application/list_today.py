"""list_today use case — the read aggregation (D157).

Composes the OPEN Cases (via the ``OpenCasesReader`` consumer port), the
Commitments-with-activity (via the ``CommitmentRepository``), and the
persisted per-day states (via the ``DayRepository``), then delegates the
status computation, default prioritisation, and ordering to the pure
``build_today_view`` domain function. ``now`` is minted here so the
domain stays deterministic; the day is the UTC date of ``now`` (a
single-timezone simplification for the Phase 2-A dogfooding instance —
operator-timezone day boundaries are a Phase 2-B refinement).
"""

from __future__ import annotations

from datetime import datetime, timezone

from contexts.daily_driver.domain.today_item import TodayView
from contexts.daily_driver.domain.view_builder import build_today_view
from contexts.daily_driver.ports.commitment_repository import (
    CommitmentRepository,
)
from contexts.daily_driver.ports.day_repository import DayRepository
from contexts.daily_driver.ports.open_cases_reader import OpenCasesReader
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_TODAY_READ,
    requires_authorisation,
)


@requires_authorisation(DAILY_DRIVER_TODAY_READ)
async def list_today(
    *,
    open_cases_reader: OpenCasesReader,
    commitment_repository: CommitmentRepository,
    day_repository: DayRepository,
    actor: ActorContext,
) -> TodayView:
    """Build the actor's prioritised-today list for the current UTC day."""
    now = datetime.now(timezone.utc)
    day_date = now.date()
    open_cases = await open_cases_reader.list_open_cases(actor=actor)
    activities = await commitment_repository.list_with_activity(
        tenant_context=actor.tenant_context
    )
    day_states = await day_repository.get_states(
        tenant_context=actor.tenant_context,
        user_id=actor.actor_id,
        day_date=day_date,
    )
    return build_today_view(
        open_cases=open_cases,
        commitment_activities=activities,
        day_states=day_states,
        now=now,
        day_date=day_date,
    )


__all__ = ["list_today"]
