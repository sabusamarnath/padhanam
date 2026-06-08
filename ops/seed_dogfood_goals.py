"""Seed the operator's remaining real dogfood goals (S69, D163/D169).

The Phase 2-A dogfood gate reads against the operator's six-plus real goals
(the brief's precondition). German (S62, progressive) and Get-a-job (S63,
sequence) are seeded by their own scripts; this script seeds the five remaining
real goals the operator supplied, spec-driven (DRY — one loop, not five
near-identical scripts, per the S65 duplication discipline):

  2. Strength        — homeostatic; 5-min micro-sessions, ≥6×/day.
  4. Wide World Marathon — progressive; a distance ladder toward the April race.
  5. Voice projection — homeostatic; daily Cheryl-Porter + own exercises.
  6. Stretch & meditate — homeostatic; daily.
  7. Litany "I will not fear" — homeostatic; 5×/day.

Each goal is an :Outcome node + a thin :Lever reference to a Postgres Commitment
(the daily/cadence practice), exactly the German/get-a-job shape. Four are the
**homeostatic** mode — schema-present since S62, instanced here for the dogfood
(the moat reads the goal facet regardless of mode; the homeostatic re-establish
*remedy* on /goals stays deferred, so a homeostatic goal reads as a graceful
hold there). Idempotent: commitments reused by deterministic id, graph MERGE
updates in place. Run inside ``padhanam-api`` via ``make seed-dogfood-goals``.

IMPORTANT (the title-linkage caveat, the [S67] finding): the moat links a unit
to a goal by a title match — a unit-facet against the **lever-commitment name**
(confirmed) or a keyword against the **goal name** (candidate). The lever names
below are the operator's best-guess; for the confirmed tier to fire, rename a
lever to match how the operator actually titles that work in the ingested
calendar/tasks. The marathon's ``current_target`` is a placeholder the operator
should set to their real current distance.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from contexts.daily_driver.domain.commitment import Commitment

log = logging.getLogger("ops.seed_dogfood_goals")

# Personal dogfood tenant (ops/dogfood_provision.py).
PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"
AUTHORED_BY = "operator-001"


@dataclass(frozen=True)
class GoalSpec:
    """One real goal to seed, mapped onto the whole-life taxonomy (D163)."""

    outcome_id: UUID
    commitment_id: UUID
    name: str
    mode: str  # "homeostatic" | "progressive"
    control: str  # "self"
    subject: str  # "self"
    lever_name: str
    expected_interval_days: int
    expected_outcome: str
    ladder: tuple[str, ...] = ()  # progressive only
    current_target_level: str | None = None  # progressive only
    # Goal-owned alias terms — category synonyms matched by the candidate
    # keyword path (D174 tier two). Category synonyms only, never per-instance
    # referential terms (no tutor names), so the residual still measures the
    # referential class honestly.
    aliases: tuple[str, ...] = ()


# Deterministic, neutral ids — encode no real identity (the dogfood precedent).
SPECS: tuple[GoalSpec, ...] = (
    GoalSpec(
        outcome_id=UUID("00000000-0000-4000-8000-0000006900a1"),
        commitment_id=UUID("00000000-0000-4000-8000-000000690c01"),
        name="Strength",
        mode="homeostatic",
        control="self",
        subject="self",
        lever_name="Strength micro-sessions",
        expected_interval_days=1,
        expected_outcome=(
            "Build strength with 5-minute micro-sessions at least 6 times a "
            "day, including seated exercises between work calls."
        ),
        aliases=("strength", "fitness", "gym", "workout", "lifting", "weights"),
    ),
    GoalSpec(
        outcome_id=UUID("00000000-0000-4000-8000-0000006900a2"),
        commitment_id=UUID("00000000-0000-4000-8000-000000690c02"),
        name="Wide World Marathon",
        mode="progressive",
        control="self",
        subject="self",
        lever_name="Marathon training run",
        expected_interval_days=2,
        expected_outcome=(
            "Train toward running the Wide World Marathon in April."
        ),
        ladder=("5K", "10K", "Half marathon", "30K", "Marathon"),
        current_target_level="Half marathon",  # operator: set to your real current rung
        aliases=("marathon", "running", "long run", "10k", "5k"),
    ),
    GoalSpec(
        outcome_id=UUID("00000000-0000-4000-8000-0000006900a3"),
        commitment_id=UUID("00000000-0000-4000-8000-000000690c03"),
        name="Voice projection",
        mode="homeostatic",
        control="self",
        subject="self",
        lever_name="Voice projection exercises",
        expected_interval_days=1,
        expected_outcome=(
            "Daily voice-projection practice — Cheryl Porter vocal exercises "
            "plus my own."
        ),
        # "articulation" dropped at S71: it floods on "Megan's articulation
        # warm-ups" (95 units — Megan's speech-therapy work, a different life
        # area), the cross-life-area collision the residual is meant to measure.
        aliases=("voice", "projection", "vocal"),
    ),
    GoalSpec(
        outcome_id=UUID("00000000-0000-4000-8000-0000006900a4"),
        commitment_id=UUID("00000000-0000-4000-8000-000000690c04"),
        name="Stretch and meditate",
        mode="homeostatic",
        control="self",
        subject="self",
        lever_name="Stretch and meditate",
        expected_interval_days=1,
        expected_outcome="Stretch and meditate daily.",
        aliases=("stretch", "stretching", "meditate", "meditation", "mobility"),
    ),
    GoalSpec(
        outcome_id=UUID("00000000-0000-4000-8000-0000006900a5"),
        commitment_id=UUID("00000000-0000-4000-8000-000000690c05"),
        name="Litany — I will not fear",
        mode="homeostatic",
        control="self",
        subject="self",
        lever_name="Litany — I will not fear",
        expected_interval_days=1,
        expected_outcome='Recite the litany "I will not fear" five times daily.',
        aliases=("litany", "mantra"),
    ),
)


async def _seed_one(spec: GoalSpec, *, commitments, graph, tenant_context) -> None:
    existing = await commitments.get_commitment(
        tenant_context=tenant_context, commitment_id=spec.commitment_id
    )
    if existing is None:
        await commitments.add_commitment(
            tenant_context=tenant_context,
            commitment=Commitment(
                id=spec.commitment_id,
                tenant_id=UUID(str(tenant_context.tenant_id)),
                jurisdiction=tenant_context.jurisdiction,
                name=spec.lever_name,
                expected_interval_days=spec.expected_interval_days,
                authored_by_user_id=AUTHORED_BY,
                created_at=datetime.now(timezone.utc),
                expected_outcome=spec.expected_outcome,
            ),
        )
        log.info("seeded lever commitment %s (%s)", spec.commitment_id, spec.lever_name)
    else:
        log.info("lever commitment %s already present, reusing", spec.commitment_id)

    await graph.merge_outcome(
        tenant_context=tenant_context,
        outcome_id=spec.outcome_id,
        name=spec.name,
        control=spec.control,
        subject=spec.subject,
        mode=spec.mode,
        ladder=spec.ladder,
        current_target_level=spec.current_target_level,
        aliases=spec.aliases,
    )
    await graph.merge_lever_for_outcome(
        tenant_context=tenant_context,
        outcome_id=spec.outcome_id,
        commitment_id=spec.commitment_id,
    )
    log.info(
        "seeded Outcome %s (%s, %s) with lever %s",
        spec.outcome_id,
        spec.name,
        spec.mode,
        spec.commitment_id,
    )


async def _seed() -> None:
    from apps.cli._runtime import build_tenant_wiring
    from contexts.daily_driver.adapters.outbound.postgres.commitment_repository import (  # noqa: E501
        PostgresCommitmentRepository,
    )
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
    graph = Neo4jGraphRepository.from_settings(Neo4jSettings())

    for spec in SPECS:
        await _seed_one(
            spec, commitments=commitments, graph=graph, tenant_context=tenant_context
        )
    log.info("seeded %d dogfood goals", len(SPECS))


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.setLevel(logging.INFO)
    log.info("seeding the operator's remaining real dogfood goals (S69)")
    asyncio.run(_seed())
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
