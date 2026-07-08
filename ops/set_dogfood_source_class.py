"""Set the dogfood get-a-job goal's source-class flag (S103ah, D240).

The correlation engine no longer names a specific job goal: it binds the rule-confirmed
job-search emails to whichever goal declares ``:Outcome.ingests_source_class ==
"email_job_search"`` (retiring the former hardcoded ``_JOB_SEARCH_GOAL_NAME``). This ops
script sets that flag on the personal dogfood tenant's get-a-job goal, so the moat count
keeps binding after the leak fix. It is **dogfood provisioning** — naming the goal here is
legitimate (the tenant UUID is dogfood-specific too), unlike the generic engine, which now
reads the flag.

Idempotent (re-running re-sets the same value) and reversible (pass ``--clear`` to remove
the flag). Ops-only, composing the goal-graph port at the boundary (the
``rescope_dogfood_to_get_a_job`` precedent). Reports counts/ids only (D21) — no goal
content. Run inside the ``padhanam-api`` container via ``make set-dogfood-source-class``.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from contexts.daily_driver.ports.email_job_search_source import (
    EMAIL_JOB_SEARCH_SOURCE_CLASS,
)

log = logging.getLogger("ops.set_dogfood_source_class")

# Personal dogfood tenant (ops/dogfood_provision.py).
PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"

# The dogfood goal that ingests the job-search email source class. Matched
# case-insensitively against the seeded Outcome name — dogfood provisioning, legitimate.
GET_A_JOB_NAME = "get a job"


async def _set(*, clear: bool) -> None:
    from apps.cli._runtime import build_tenant_wiring
    from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
    from padhanam.config import Neo4jSettings

    wiring = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tenant_context = wiring.tenant_context
    graph = Neo4jGraphRepository.from_settings(Neo4jSettings())
    try:
        outcomes = await graph.list_outcomes(tenant_context=tenant_context)
        target = [o for o in outcomes if o.name.strip().lower() == GET_A_JOB_NAME]
        if not target:
            log.warning(
                "get-a-job not found among %d active goals — nothing to set; seed it "
                "first", len(outcomes),
            )
            return
        value = None if clear else EMAIL_JOB_SEARCH_SOURCE_CLASS
        for o in target:
            ok = await graph.set_outcome_source_class(
                tenant_context=tenant_context, outcome_id=o.outcome_id,
                source_class=value,
            )
            log.info(
                "%s ingests_source_class on goal %s: %s",
                "cleared" if clear else "set", o.outcome_id, "ok" if ok else "not found",
            )
    finally:
        await graph.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clear", action="store_true",
        help="remove the flag instead of setting it (reverse)",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.setLevel(logging.INFO)
    asyncio.run(_set(clear=args.clear))
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
