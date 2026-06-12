"""Surface each goal's status on the live corpus for the S92 sanity-check (D187).

Read-only. Runs the real ``list_units_by_goal`` projection (the surface's read
path) for the personal tenant and prints, per goal, the computed status and the
evidence that drove it — the mode, the lever cadences + last completions (cadence
goals), the latest confirmed-edge activity date (cadence-less). Counts and dates
only; no unit titles, no content. The operator sanity-checks that the verdicts
read true (a goal that stopped reads stalled; one met at cadence reads on-track).

Run inside ``padhanam-api`` (``make goal-status-report``).
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone

from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles

log = logging.getLogger("ops.goal_status_report")
PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"


async def _report() -> None:
    from apps.api._daily_driver_wiring import (
        EmailJobSearchSourceAdapter,
        FacetSourceAdapter,
        GoalGraphAdapter,
        UnitGraphAdapter,
    )
    from apps.cli._runtime import build_tenant_wiring
    from contexts.daily_driver.adapters.outbound.postgres.commitment_repository import (  # noqa: E501
        PostgresCommitmentRepository,
    )
    from contexts.daily_driver.application import list_units_by_goal
    from contexts.daily_driver.domain.goal import GoalMode
    from contexts.daily_driver.domain.goal_status import _goal_lever_ids
    from contexts.daily_driver.domain.staleness import (
        days_elapsed,
        overdue_by_days,
    )
    from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
    from padhanam.config import Neo4jSettings
    from shared_kernel import ActorContext, TenantContext, TenantId

    wiring = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tc: TenantContext = wiring.tenant_context
    sf = wiring.session_factory

    async def _sf(_t):
        return sf

    async def _resolver(_t):
        return sf

    graph = Neo4jGraphRepository.from_settings(Neo4jSettings())
    facet_source = FacetSourceAdapter(session_factory_for_tenant=_sf)
    goal_graph = GoalGraphAdapter(outcome_graph=graph)
    unit_graph = UnitGraphAdapter(unit_graph=graph)
    email_source = EmailJobSearchSourceAdapter(session_factory_for_tenant=_sf)
    commitment_repository = PostgresCommitmentRepository(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=TenantId(str(tc.tenant_id)),
    )
    roles = frozenset({ROLE_OPERATOR})
    actor = ActorContext(
        tenant_context=tc, actor_id="ops.goal_status_report",
        role_list=roles, authorisation_set=authorisations_for_roles(roles),
    )
    now = datetime.now(timezone.utc)

    # The real read-path projection (status computed inside).
    grouped = await list_units_by_goal(
        unit_graph=unit_graph, facet_source=facet_source, goal_graph=goal_graph,
        actor=actor, email_job_search_source=email_source,
        commitment_repository=commitment_repository, now=now,
    )

    # Evidence (recomputed for transparency — dates/counts only).
    goals = {g.id: g for g in await goal_graph.list_goals(tenant_context=tc)}
    acts = {
        a.commitment.id: a
        for a in await commitment_repository.list_with_activity(tenant_context=tc)
    }

    log.info("S92 goal status on the live corpus (n=%d goals shown):", len(grouped.groups))
    for grp in grouped.groups:
        goal = goals.get(grp.outcome_id)
        status = grp.status.value if grp.status is not None else "(none)"
        why = grp.status_why or ""
        mode = goal.mode.value if goal is not None else "?"
        ev: list[str] = []
        if goal is not None and goal.mode is GoalMode.HOMEOSTATIC:
            for cid in _goal_lever_ids(goal):
                a = acts.get(cid)
                if a is None:
                    continue
                interval = a.commitment.expected_interval_days
                last = a.last_completed_at or a.commitment.created_at
                od = overdue_by_days(
                    last_activity_at=last, expected_interval_days=interval, now=now,
                )
                tag = "never-done" if a.last_completed_at is None else "done"
                ev.append(
                    f"lever(int={interval}d, {tag}, {od}d overdue, "
                    f"{od // interval} missed)"
                )
        # latest confirmed-edge activity (units shown / email)
        n_units = len(grp.units)
        n_email = sum(c for _, c in grp.email_activity)
        ev.append(f"units={n_units} email={n_email}")
        log.info(
            "  %-26s [%s]  %-9s · %-12s   %s",
            (goal.name if goal else "?"), mode, status, why, " ".join(ev),
        )


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(message)s", stream=sys.stdout
    )
    log.setLevel(logging.INFO)
    asyncio.run(_report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
