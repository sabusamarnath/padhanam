"""Seed German as the first end-to-end causal goal (S62, D163).

Instances the progressive-cadence / control-self / subject-self shape of the
whole-life goal taxonomy in the personal dogfood tenant:

  - a German-practice **Commitment** in per-tenant Postgres (the lever), reused
    if it already exists and seeded minimally otherwise;
  - an **:Outcome** node in the shared graph (the goal), mode progressive,
    control self, subject self, with a CEFR level ladder toward fluency and a
    current target one level above where the operator sits (A2 → B1);
  - a **LEVER_FOR** edge connecting the commitment-as-lever to the outcome.

Ops-only, no domain code beyond the daily-driver/ingestion ports it composes at
the boundary (the calendar-CLI precedent: the apps/ops composition root may wire
concrete adapters). Idempotent: re-running reuses the commitment by its
deterministic id and the graph MERGE updates in place. Must run where the
personal-tenant Postgres host resolves and Neo4j is reachable (inside the
``padhanam-api`` container, via ``make seed-german``), mirroring
``ops/dogfood_provision.py``.

The graph is tenant-property scoped (D63), so the Outcome/Lever/edge carry the
personal tenant's id + jurisdiction and are reached only through the
``Neo4jGraphRepository`` (no raw driver call). The target changes only on the
operator's explicit raise (D9); seeding sets the initial target, not a ramp.
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

log = logging.getLogger("ops.seed_german_goal")

# Personal dogfood tenant (ops/dogfood_provision.py).
PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"

# Deterministic, neutral ids — encode no real identity (the dogfood precedent).
GERMAN_COMMITMENT_ID = UUID("00000000-0000-4000-8000-000000620c01")
GERMAN_OUTCOME_ID = UUID("00000000-0000-4000-8000-0000006200a1")

# The lever: a daily German-practice commitment with a forward expectation.
GERMAN_COMMITMENT_NAME = "German practice"
GERMAN_EXPECTED_INTERVAL_DAYS = 1
GERMAN_EXPECTED_OUTCOME = (
    "Daily practice that moves my German toward conversational fluency."
)
GERMAN_AUTHORED_BY = "operator-001"

# The goal: a progressive-cadence outcome with a qualitative CEFR ladder. The
# operator sits at A2; the current target is one level above (B1) per D163.
GERMAN_LADDER = ("A1", "A2", "B1", "B2", "C1", "C2")
GERMAN_CURRENT_TARGET = "B1"


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

    # 1. The lever commitment — reuse if present, seed minimally otherwise.
    existing = await commitments.get_commitment(
        tenant_context=tenant_context, commitment_id=GERMAN_COMMITMENT_ID
    )
    if existing is None:
        commitment = Commitment(
            id=GERMAN_COMMITMENT_ID,
            tenant_id=UUID(str(tenant_context.tenant_id)),
            jurisdiction=tenant_context.jurisdiction,
            name=GERMAN_COMMITMENT_NAME,
            expected_interval_days=GERMAN_EXPECTED_INTERVAL_DAYS,
            authored_by_user_id=GERMAN_AUTHORED_BY,
            created_at=datetime.now(timezone.utc),
            expected_outcome=GERMAN_EXPECTED_OUTCOME,
        )
        await commitments.add_commitment(
            tenant_context=tenant_context, commitment=commitment
        )
        log.info("seeded German-practice commitment %s", GERMAN_COMMITMENT_ID)
    else:
        log.info(
            "German-practice commitment %s already present, reusing as lever",
            GERMAN_COMMITMENT_ID,
        )

    # 1b. Clear the synthetic `met` observation the S62 live smoke left on the
    # German lever (AC10). This is ops test-pollution cleanup, not a product
    # capability — the observation was never user-authored, so clearing it does
    # not breach the no-auto-deletion invariant (which guards user content). The
    # dogfooding week starts from a clean slate (no observation, target reads
    # B1). Done via a direct update through the bound sessionmaker (ops
    # composition root may compose adapters and issue the cleanup write).
    await _clear_observation(session_factory, tenant_context)

    # 2. The Outcome node + the lever-to-outcome edge in the shared graph. Per
    # the D163 clarification (S63), mode + ladder + current target are
    # goal-level properties on the :Outcome node; the edge carries only that the
    # lever serves the outcome.
    graph = Neo4jGraphRepository.from_settings(Neo4jSettings())
    try:
        await graph.merge_outcome(
            tenant_context=tenant_context,
            outcome_id=GERMAN_OUTCOME_ID,
            name="German",
            control="self",
            subject="self",
            mode="progressive",
            ladder=GERMAN_LADDER,
            current_target_level=GERMAN_CURRENT_TARGET,
        )
        await graph.merge_lever_for_outcome(
            tenant_context=tenant_context,
            outcome_id=GERMAN_OUTCOME_ID,
            commitment_id=GERMAN_COMMITMENT_ID,
        )
        log.info(
            "seeded Outcome %s (German, progressive) with lever edge to %s; "
            "current target %s on ladder %s",
            GERMAN_OUTCOME_ID,
            GERMAN_COMMITMENT_ID,
            GERMAN_CURRENT_TARGET,
            "/".join(GERMAN_LADDER),
        )
    finally:
        await graph.close()


async def _clear_observation(session_factory, tenant_context) -> None:
    """Null the German lever's observation fields (AC10 — clear the S62 smoke's
    synthetic `met`). Idempotent: a clean lever stays clean."""
    import sqlalchemy as sa

    from contexts.daily_driver.adapters.outbound.postgres._tables import (
        commitments as commitments_table,
    )

    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                sa.update(commitments_table)
                .where(
                    sa.and_(
                        commitments_table.c.id == str(GERMAN_COMMITMENT_ID),
                        commitments_table.c.tenant_id
                        == str(tenant_context.tenant_id),
                    )
                )
                .values(
                    observed_outcome=None,
                    outcome_status=None,
                    observed_at=None,
                )
            )
    log.info("cleared any synthetic observation on German lever %s", GERMAN_COMMITMENT_ID)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.setLevel(logging.INFO)
    log.info("seeding German as the first progressive-cadence goal (S62)")
    asyncio.run(_seed())
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
