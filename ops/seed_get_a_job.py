"""Seed get-a-job as the second end-to-end causal goal (S63, D163).

Instances the **sequence / control-influence / subject-self** shape of the
whole-life goal taxonomy in the personal dogfood tenant — the second goal,
proving the taxonomy generalises across engine (cadence → sequence) and remedy
(raise-or-hold → unblock-or-drop) rather than needing a rebuild:

  - a chain of **lever-step Commitments** in per-tenant Postgres (the steps the
    actor controls), reused if present and seeded minimally otherwise;
  - an **:Outcome** node in the shared graph (the goal), mode ``sequence``,
    control ``other`` (the influence case — another party, the employer,
    determines the terminal; the actor only influences it), subject ``self``,
    with a **terminal target** representing the goal reached once ("Offer
    accepted") rather than a level ladder, and a ``terminal_state`` of
    ``pending`` (the influence-gated part, richer reading deferred to the
    influence instance);
  - a **LEVER_FOR** edge per step carrying ``step_order`` + ``step_state``, the
    chain releasing toward the terminal.

control ``other`` is recorded as a field value only; no influence-specific logic
is built, consistent with the schema-present, uninstanced discipline (S62).

Ops-only, no domain code beyond the ports it composes at the boundary (the
seed_german_goal precedent). Idempotent: re-running reuses commitments by their
deterministic ids and the graph MERGE updates in place. Run inside the
``padhanam-api`` container via ``make seed-get-a-job``.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from uuid import UUID

from contexts.daily_driver.adapters.outbound.postgres.commitment_repository import (  # noqa: E501
    PostgresCommitmentRepository,
)
from contexts.daily_driver.domain.commitment import Commitment

log = logging.getLogger("ops.seed_get_a_job")

# Personal dogfood tenant (ops/dogfood_provision.py).
PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"

# Deterministic, neutral ids — encode no real identity (the dogfood precedent).
GET_A_JOB_OUTCOME_ID = UUID("00000000-0000-4000-8000-0000006300a1")

GET_A_JOB_AUTHORED_BY = "operator-001"

# The terminal — the goal reached once, the part the employer decides (control
# influence). Represented as a state; the probabilistic did-my-influence-land
# reading is deferred to the influence instance.
GET_A_JOB_TERMINAL_TARGET = "Offer accepted"

# The chain of lever steps the actor controls, releasing toward the terminal.
# step 1 is done; step 2 is the active step and is blocked (the real blocker the
# unblock-or-drop remedy reads); step 3 waits on step 2. (order, name, interval
# days, step_state.)
GET_A_JOB_STEPS = (
    (
        UUID("00000000-0000-4000-8000-0000006300c1"),
        1,
        "Refresh CV and portfolio",
        7,
        "done",
    ),
    (
        UUID("00000000-0000-4000-8000-0000006300c2"),
        2,
        "Apply to target roles",
        3,
        "blocked",
    ),
    (
        UUID("00000000-0000-4000-8000-0000006300c3"),
        3,
        "Interview preparation",
        7,
        "blocked",
    ),
)


async def _seed() -> None:
    from apps.cli._runtime import build_tenant_wiring
    from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
    from padhanam.config import Neo4jSettings
    from shared_kernel import TenantId

    wiring = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tenant_context = wiring.tenant_context
    session_factory = wiring.session_factory

    async def _resolver(_tid: TenantId):
        return session_factory

    bound = TenantId(str(tenant_context.tenant_id))
    commitments = PostgresCommitmentRepository(
        per_tenant_sessionmaker_resolver=_resolver, bound_tenant_id=bound
    )

    # 1. The lever-step commitments — reuse if present, seed minimally otherwise.
    for commitment_id, order, name, interval_days, _state in GET_A_JOB_STEPS:
        existing = await commitments.get_commitment(
            tenant_context=tenant_context, commitment_id=commitment_id
        )
        if existing is None:
            commitment = Commitment(
                id=commitment_id,
                tenant_id=UUID(str(tenant_context.tenant_id)),
                jurisdiction=tenant_context.jurisdiction,
                name=name,
                expected_interval_days=interval_days,
                authored_by_user_id=GET_A_JOB_AUTHORED_BY,
                created_at=datetime.now(timezone.utc),
                expected_outcome=f"Step {order} toward a new role: {name}.",
            )
            await commitments.add_commitment(
                tenant_context=tenant_context, commitment=commitment
            )
            log.info("seeded lever-step commitment %s (%s)", commitment_id, name)
        else:
            log.info(
                "lever-step commitment %s (%s) already present, reusing",
                commitment_id,
                name,
            )

    # 2. The Outcome node (sequence, control influence, subject self, terminal)
    # + a lever edge per step carrying step_order + step_state.
    graph = Neo4jGraphRepository.from_settings(Neo4jSettings())
    try:
        await graph.merge_outcome(
            tenant_context=tenant_context,
            outcome_id=GET_A_JOB_OUTCOME_ID,
            name="Get a job",
            control="other",  # the influence case — the employer determines it
            subject="self",
            mode="sequence",
            ladder=(),  # a terminal, not a ladder
            current_target_level=None,
            terminal_target=GET_A_JOB_TERMINAL_TARGET,
            terminal_state="pending",  # influence-gated; awaiting the employer
        )
        for commitment_id, order, name, _interval, state in GET_A_JOB_STEPS:
            await graph.merge_lever_for_outcome(
                tenant_context=tenant_context,
                outcome_id=GET_A_JOB_OUTCOME_ID,
                commitment_id=commitment_id,
                step_order=order,
                step_state=state,
            )
        log.info(
            "seeded Outcome %s (Get a job, sequence) with %d lever steps; "
            "terminal '%s' (pending, influence-gated)",
            GET_A_JOB_OUTCOME_ID,
            len(GET_A_JOB_STEPS),
            GET_A_JOB_TERMINAL_TARGET,
        )
    finally:
        await graph.close()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.setLevel(logging.INFO)
    log.info("seeding get-a-job as the second goal, a sequence (S63)")
    asyncio.run(_seed())
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
