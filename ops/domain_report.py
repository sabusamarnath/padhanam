"""Commitment-domain resolution report for the personal dogfood tenant (S82, D179).

The standing instrument for judging the domain-from-goal resolution: reads the
live goals (each carrying its `domain`, D179) and the live commitments, builds
the `commitment_id -> goal.domain` map the Today surface uses, and prints per
goal its domain + how many of its lever-commitments resolve, plus the corpus
summary (how many commitments each domain now carries, versus the pre-D179
"every commitment is work" baseline) and a mis-domain check.

Grouped by goal so the report never prints an individual commitment name — the
health-regimen levers are medication titles kept local (the S80 discipline).

Read-only — computes nothing, writes nothing. Run via `make domain-report`.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections import Counter

log = logging.getLogger("ops.domain_report")

# Personal dogfood tenant (ops/dogfood_provision.py).
PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"


async def _report() -> None:
    from apps.api._daily_driver_wiring import build_goal_graph
    from apps.cli._runtime import build_tenant_wiring
    from contexts.daily_driver.adapters.outbound.postgres.commitment_repository import (
        PostgresCommitmentRepository,
    )
    from contexts.daily_driver.domain.goal_assessment import (
        _goal_commitment_ids,
        commitment_domains_from_goals,
    )
    from shared_kernel import TenantId

    wiring = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tenant_context = wiring.tenant_context
    session_factory = wiring.session_factory

    async def _resolver(_tid: TenantId):
        return session_factory

    goal_graph = build_goal_graph()
    goals = await goal_graph.list_goals(tenant_context=tenant_context)
    commitment_domains = commitment_domains_from_goals(goals)

    repo = PostgresCommitmentRepository(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=TenantId(str(tenant_context.tenant_id)),
    )
    activities = await repo.list_with_activity(tenant_context=tenant_context)

    print("\n=== Commitment-domain resolution report (S82, D179) ===")
    print(
        "Before D179 every Commitment row rendered 'work'. After D179 a "
        "commitment takes the domain of the goal it levers.\n"
    )
    print("per goal:")
    for goal in sorted(goals, key=lambda g: g.name.lower()):
        n_levers = len(_goal_commitment_ids(goal))
        print(
            f"  {goal.name:<26} domain={goal.domain or '(unset)'!s:<10} "
            f"{n_levers} lever-commitment(s)"
        )

    # Corpus summary + mis-domain check over the surface commitment set.
    after: Counter[str] = Counter()
    for act in activities:
        after[commitment_domains.get(act.commitment.id, "work")] += 1
    total = len(activities)
    print(
        f"\ncommitments on the surface: {total}\n"
        f"  before D179:  work {total}\n"
        f"  after  D179:  "
        + ", ".join(f"{d} {n}" for d, n in sorted(after.items()))
    )

    # Mis-domain check: every lever of a domained goal must resolve to that
    # goal's domain; nothing levering a personal goal may read work.
    mis = 0
    levered = {
        cid: goal
        for goal in goals
        if goal.domain is not None
        for cid in _goal_commitment_ids(goal)
    }
    for act in activities:
        goal = levered.get(act.commitment.id)
        if goal is None:
            continue
        resolved = commitment_domains.get(act.commitment.id, "work")
        from contexts.daily_driver.domain.calendar_domain import (
            resolve_calendar_domain,
        )

        if resolved != resolve_calendar_domain(goal.domain):
            mis += 1
    print(
        f"\nmis-domained commitments (levered-goal domain != resolved): {mis}"
        + ("  OK" if mis == 0 else "  <-- INVESTIGATE")
    )
    print()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.setLevel(logging.INFO)
    log.info("domain report for the personal dogfood tenant (S82, D179)")
    asyncio.run(_report())
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
