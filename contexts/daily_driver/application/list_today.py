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

from contexts.daily_driver.domain.goal_assessment import (
    commitment_domains_from_goals,
)
from contexts.daily_driver.domain.today_item import CalendarToday, TodayView
from contexts.daily_driver.domain.view_builder import build_today_view
from contexts.daily_driver.ports.calendar_events_reader import (
    CalendarEventsReader,
)
from contexts.daily_driver.ports.commitment_repository import (
    CommitmentRepository,
)
from contexts.daily_driver.ports.day_repository import DayRepository
from contexts.daily_driver.ports.goal_graph import GoalGraphPort
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
    calendar_events_reader: CalendarEventsReader | None = None,
    goal_graph: GoalGraphPort | None = None,
    drop_candidate_quiet_days: int | None = None,
    now: datetime | None = None,
) -> TodayView:
    """Build the actor's prioritised-today list for the current UTC day.

    The calendar source is optional (D159): when no reader is wired — or
    no calendar is connected for the tenant — the list is the S58/S59
    Cases-plus-Commitments view, so the surface degrades cleanly rather
    than failing for an unconnected operator.

    ``drop_candidate_quiet_days`` (D162) is the configured quiet-window
    threshold for the drop-candidate recommendation; ``None`` disables the
    flag (the S60 view).

    ``now`` is the injectable clock (S64): the today window + the D157 staleness
    compute resolve against it, defaulting to the wall clock in production.
    """
    now = now or datetime.now(timezone.utc)
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
    calendar_events: tuple[CalendarToday, ...] = ()
    if calendar_events_reader is not None:
        calendar_events = await calendar_events_reader.list_today_events(
            actor=actor, day_date=day_date
        )
    # D179: a commitment that levers a goal takes the goal's domain. The map is
    # absent (every commitment → work default) when no goal graph is wired, so
    # the surface degrades to the pre-D179 view rather than failing.
    commitment_domains: dict = {}
    if goal_graph is not None:
        goals = await goal_graph.list_goals(tenant_context=actor.tenant_context)
        commitment_domains = commitment_domains_from_goals(goals)
    return build_today_view(
        open_cases=open_cases,
        commitment_activities=activities,
        day_states=day_states,
        now=now,
        day_date=day_date,
        calendar_events=calendar_events,
        drop_candidate_quiet_days=drop_candidate_quiet_days,
        commitment_domains=commitment_domains,
    )


__all__ = ["list_today"]
