"""Re-scope the personal dogfood tenant to get-a-job (S103e, D205).

The clean-data move before the get-a-job framework-driven CDD authoring: archive
every authored goal **except** get-a-job, reversibly, with nothing erased. Tuning
the matcher across eight goals on a two-thirds-unbound corpus produced abstract
questions; a clean single-goal corpus makes the matcher's get-a-job binds
readable by eye (D200's authored-and-corrected model).

Archive, never erase (user-safety invariant 4 + originals-never-erased): each
non-target goal is marked archived via ``OutcomeGraphPort.archive_outcome``
(a schemaless ``:Outcome.archived_at`` marker). The goal node, its authored CDD
elements, its ``EVIDENCES`` binds and its audit history all stay intact. The
assess surface (List/Map/CDD) and the matcher read active goals only through the
single ``list_goals`` seam, so archived goals drop out of both reads.

Idempotent (re-running re-archives the already-archived, a no-op set) and
reversible: ``--reactivate`` removes every archive marker, returning the goals
whole. Ops-only, composing the goal-graph port at the boundary (the
``seed_get_a_job`` precedent). Reports counts and ids only (D21) — no content.
Run inside the ``padhanam-api`` container via ``make rescope-dogfood`` (or the
``--reactivate`` reverse). Counts/shape only, never goal content.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

log = logging.getLogger("ops.rescope_dogfood_to_get_a_job")

# Personal dogfood tenant (ops/dogfood_provision.py).
PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"

# The one goal that stays active. Matched case-insensitively against the seeded
# Outcome name ("Get a job"); the same name the matcher keys on
# (correlate_goal_facets._JOB_SEARCH_GOAL_NAME).
GET_A_JOB_NAME = "get a job"


async def _rescope(*, reactivate: bool) -> None:
    from apps.cli._runtime import build_tenant_wiring
    from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
    from padhanam.config import Neo4jSettings

    wiring = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tenant_context = wiring.tenant_context

    graph = Neo4jGraphRepository.from_settings(Neo4jSettings())
    try:
        # list_outcomes scopes to active goals, so an archived goal no longer
        # appears here. Archiving reads the active set and marks every non-target;
        # reactivation cannot re-list (archived rows are hidden), so it targets
        # the seeded goal ids directly.
        if reactivate:
            await _reactivate_all(graph, tenant_context)
            return

        outcomes = await graph.list_outcomes(tenant_context=tenant_context)
        target = [
            o for o in outcomes if o.name.strip().lower() == GET_A_JOB_NAME
        ]
        others = [
            o for o in outcomes if o.name.strip().lower() != GET_A_JOB_NAME
        ]
        if not target:
            log.warning(
                "get-a-job not found among %d active goals — refusing to "
                "archive (would leave the corpus goalless); seed it first",
                len(outcomes),
            )
            return
        log.info(
            "active goals before: %d (get-a-job present); archiving %d others",
            len(outcomes),
            len(others),
        )
        archived = 0
        for o in others:
            ok = await graph.archive_outcome(
                tenant_context=tenant_context, outcome_id=o.outcome_id
            )
            if ok:
                archived += 1
                log.info("archived goal %s", o.outcome_id)
            else:
                log.warning("goal %s not found on archive", o.outcome_id)
        remaining = await graph.list_outcomes(tenant_context=tenant_context)
        log.info(
            "archived %d goals; active goals now: %d (%s)",
            archived,
            len(remaining),
            ", ".join(o.outcome_id.hex for o in remaining),
        )
    finally:
        await graph.close()


async def _reactivate_all(graph, tenant_context) -> None:
    """Reverse the re-scope by unarchiving the **actual** archived set — read the
    archived ids straight from the graph (the complement of the active list), so
    reactivation restores every archived goal whole and cannot drift from what was
    archived (it does not depend on knowing the seed modules)."""
    archived = await graph.list_archived_outcome_ids(
        tenant_context=tenant_context
    )
    returned = 0
    for oid in archived:
        ok = await graph.unarchive_outcome(
            tenant_context=tenant_context, outcome_id=oid
        )
        if ok:
            returned += 1
            log.info("reactivated goal %s", oid)
    active = await graph.list_outcomes(tenant_context=tenant_context)
    log.info(
        "reactivated %d goals; active goals now: %d", returned, len(active)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reactivate",
        action="store_true",
        help="reverse the re-scope: unarchive every seeded goal (returns whole)",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.setLevel(logging.INFO)
    if args.reactivate:
        log.info("reactivating all personal-tenant goals (reverse the re-scope)")
    else:
        log.info("re-scoping the personal dogfood tenant to get-a-job (S103e)")
    asyncio.run(_rescope(reactivate=args.reactivate))
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
