"""Assessment coverage report for the personal dogfood tenant (S71, D174).

The standing instrument for judging every linkage change: reads the live graph —
the persisted ``SERVES`` edges that the assessment read treats as source of truth
(D169) — and prints, per goal, whether it is **linked** (count + tier) or
**uncovered**; the total **orphan**-unit count (units with no goal edge); and a
sample of orphan titles. This is the metric the embedding-tier decision waits on
(D174): read the orphan sample, quantify the residual referential class, and
decide whether tier three is warranted or a few more aliases close the gap.

Read-only — computes nothing, writes nothing, recommends nothing. Run after a
fresh ``make correlate-units`` inside ``padhanam-api`` via
``make coverage-report``.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections import Counter, defaultdict

log = logging.getLogger("ops.coverage_report")

# Personal dogfood tenant (ops/dogfood_provision.py).
PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"

_ORPHAN_SAMPLE = 20


async def _report() -> None:
    from apps.api._daily_driver_wiring import (
        FacetSourceAdapter,
        GoalGraphAdapter,
        UnitGraphAdapter,
    )
    from apps.cli._runtime import build_tenant_wiring
    from contexts.daily_driver.application.list_goal_assessment import (
        list_goal_assessment,
    )
    from contexts.ingestion.adapters.outbound.neo4j import (
        Neo4jGraphRepository,
    )
    from padhanam.config import Neo4jSettings
    from shared_kernel import ActorContext
    from shared_kernel.authorisation import (
        ROLE_OPERATOR,
        authorisations_for_roles,
    )

    wiring = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tenant_context = wiring.tenant_context
    session_factory = wiring.session_factory

    async def _session_factory_for_tenant(_tc):
        return session_factory

    graph = Neo4jGraphRepository.from_settings(Neo4jSettings())
    facet_source = FacetSourceAdapter(
        session_factory_for_tenant=_session_factory_for_tenant
    )
    unit_graph = UnitGraphAdapter(unit_graph=graph)
    goal_graph = GoalGraphAdapter(outcome_graph=graph)

    roles = frozenset({ROLE_OPERATOR})
    actor = ActorContext(
        tenant_context=tenant_context,
        actor_id="ops.coverage_report",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )

    goals = await goal_graph.list_goals(tenant_context=tenant_context)
    edges = await unit_graph.list_goal_edges(tenant_context=tenant_context)
    assessment = await list_goal_assessment(
        unit_graph=unit_graph,
        facet_source=facet_source,
        goal_graph=goal_graph,
        actor=actor,
    )

    edges_by_goal: dict = defaultdict(list)
    for e in edges:
        edges_by_goal[e.outcome_id].append(e)

    cov = assessment.coverage
    print("\n=== Assessment coverage report (S71, D174) ===")
    print(
        f"coverage: {cov.goals_covered}/{cov.goals_total} goals linked, "
        f"{cov.units_linked}/{cov.units_total} units linked, "
        f"has_coverage={cov.has_coverage}\n"
    )

    print("per goal:")
    for goal in sorted(goals, key=lambda g: g.name.lower()):
        goal_edges = edges_by_goal.get(goal.id, [])
        if goal_edges:
            tiers = Counter(e.status.value for e in goal_edges)
            tier_str = ", ".join(f"{n} {s}" for s, n in sorted(tiers.items()))
            print(f"  LINKED    {goal.name:<26} {len(goal_edges)} units ({tier_str})")
        else:
            print(f"  uncovered {goal.name:<26} (Padhanam can't see work for this)")

    orphans = assessment.orphan_work
    print(f"\norphan units (no goal edge): {len(orphans)}")
    if not cov.has_coverage:
        print("  (orphan read suppressed — no coverage yet, D171)")
    sample = orphans[:_ORPHAN_SAMPLE]
    if sample:
        print(f"\nsample of {len(sample)} orphan titles (of {len(orphans)}):")
        for o in sample:
            print(f"  · {o.title}")
    print()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.setLevel(logging.INFO)
    log.info("coverage report for the personal dogfood tenant (S71, D174)")
    asyncio.run(_report())
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
