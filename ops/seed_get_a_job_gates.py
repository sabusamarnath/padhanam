"""Author the Apply and Screening gate CDDs from the framework (S103g, D207).

Slice two-A: the first build of the step-as-portal depth. Seeds two process-flow
gates (Apply, Screening) on get-a-job, each a portal into its local CDD with
Pratt's wiring — levers FEED the intermediary, externals INFLUENCE the
intermediary, the intermediary FEEDS the gate (the gate node is the local-outcome
endpoint). Gate elements carry gate_id (their gate) + outcome_id (the goal, so
gate work still rolls up to goal coverage). Provenance llm_drafted / pending; the
operator proofs after the session.

The re-homing (D207): the goal-level ``Tailoring effort`` lever **relocates** into
the Apply gate — same node, its live provenance + proof state carried (it is
llm_drafted, the merge of Tailored resume was a delete-of-duplicate, no fold), its
goal-level FEEDS edge **migrated** (the old lever→intermediary edge dropped, the
gate one added) so the goal CDD's edge count stays clean and nothing double-counts.
The genuine portfolio levers stay at goal level; the two user_authored stage
intermediaries are preserved in place (their connection to the interview gates is
slice two-C, when those gates exist).

Idempotent (MERGE + idempotent relocate + idempotent edge delete). Ops-only,
counts/ids on the log (D21). Run inside padhanam-api via make seed-get-a-job-gates;
then make correlate-units to bind work to the gate elements.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from uuid import UUID

log = logging.getLogger("ops.seed_get_a_job_gates")

PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"
GET_A_JOB_OUTCOME_ID = UUID("00000000-0000-4000-8000-0000006300a1")

# The goal-level Tailoring effort lever (slice one) + its current goal edge target
# (Aggregate win-probability) — relocated into the Apply gate.
TAILORING_EFFORT_ID = UUID("00000000-0000-4000-8000-00000063f003")
GOAL_WIN_PROBABILITY_ID = UUID("00000000-0000-4000-8000-00000063f102")

# D163 step 2 (Apply to target roles) — the Apply gate references it.
APPLY_STEP_COMMITMENT_ID = UUID("00000000-0000-4000-8000-0000006300c2")

# --- Apply gate -------------------------------------------------------------
APPLY_GATE_ID = UUID("00000000-0000-4000-8000-0000063a0001")
APPLY_SCREEN_THROUGH_ID = UUID("00000000-0000-4000-8000-0000063a1101")
# New Apply levers (Tailoring effort relocates in, so it is not seeded here).
APPLY_LEVERS = (
    (UUID("00000000-0000-4000-8000-0000063a1001"),
     "Referral pursuit: chase a warm referral into the role"),
    (UUID("00000000-0000-4000-8000-0000063a1002"),
     "Time budget: how much effort this application is worth"),
    (UUID("00000000-0000-4000-8000-0000063a1003"),
     "Recruiter as advocate: brief the recruiter to champion you"),
)
APPLY_EXTERNALS = (
    (UUID("00000000-0000-4000-8000-0000063a1201"),
     "JD match: how well the role description fits your profile"),
    (UUID("00000000-0000-4000-8000-0000063a1202"),
     "Applicant pool size: how many others are competing"),
    (UUID("00000000-0000-4000-8000-0000063a1203"),
     "Referral availability: whether a warm intro exists"),
    (UUID("00000000-0000-4000-8000-0000063a1204"),
     "Role wired for an internal candidate"),
)

# --- Screening gate ---------------------------------------------------------
SCREENING_GATE_ID = UUID("00000000-0000-4000-8000-0000063a0002")
SCREENING_CLEARING_ID = UUID("00000000-0000-4000-8000-0000063a2101")
SCREENING_LEVERS = (
    (UUID("00000000-0000-4000-8000-0000063a2001"),
     "Take-home quality and time: investment in the take-home or assessment"),
    (UUID("00000000-0000-4000-8000-0000063a2002"),
     "Assessment preparation: prep for the online assessment"),
    (UUID("00000000-0000-4000-8000-0000063a2003"),
     "Clarifying expectations with the recruiter"),
)
SCREENING_EXTERNALS = (
    (UUID("00000000-0000-4000-8000-0000063a2201"),
     "Recruiter screen: the recruiter's filter"),
    (UUID("00000000-0000-4000-8000-0000063a2202"),
     "Take-home design: how the take-home is structured"),
    (UUID("00000000-0000-4000-8000-0000063a2203"),
     "Online assessment cut-offs"),
)


async def _seed() -> None:
    from apps.cli._runtime import build_tenant_wiring
    from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
    from padhanam.config import Neo4jSettings

    wiring = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tc = wiring.tenant_context
    g = Neo4jGraphRepository.from_settings(Neo4jSettings())

    async def merge_el(kind, eid, label, gate_id):
        await g.merge_authored_element(
            tenant_context=tc, outcome_id=GET_A_JOB_OUTCOME_ID,
            element_kind=kind, element_id=eid, label=label,
            provenance_origin="llm_drafted", proof_state="pending",
            gate_id=gate_id,
        )

    async def feeds(skind, sid, tkind, tid):
        await g.merge_authored_edge(
            tenant_context=tc, edge_type="FEEDS",
            source_kind=skind, source_id=sid, target_kind=tkind, target_id=tid,
        )

    async def influences(sid, tid):
        await g.merge_authored_edge(
            tenant_context=tc, edge_type="INFLUENCES",
            source_kind="external", source_id=sid,
            target_kind="intermediary", target_id=tid,
        )

    try:
        # 1. The two gates (the local-outcome endpoints).
        await g.merge_gate(
            tenant_context=tc, gate_id=APPLY_GATE_ID,
            outcome_id=GET_A_JOB_OUTCOME_ID, name="Apply", gate_order=3,
            local_outcome=(
                "Expected interviews generated vs the opportunity cost of the "
                "same effort elsewhere"
            ),
            local_goal="highest return on marginal effort",
            provenance_origin="llm_drafted", proof_state="pending",
            step_commitment_id=APPLY_STEP_COMMITMENT_ID,
        )
        await g.merge_gate(
            tenant_context=tc, gate_id=SCREENING_GATE_ID,
            outcome_id=GET_A_JOB_OUTCOME_ID, name="Screening", gate_order=4,
            local_outcome=(
                "Advance vs screened out, plus early intel on band and process"
            ),
            local_goal=(
                "clear the gate efficiently without over-investing before signal "
                "exists"
            ),
            provenance_origin="llm_drafted", proof_state="pending",
            step_commitment_id=None,
        )
        log.info("seeded 2 gates (Apply gate_order=3, Screening gate_order=4)")

        # 2. Apply gate CDD. Relocate Tailoring effort in (carry provenance,
        # migrate its edge), seed the other levers/intermediary/externals.
        await g.merge_authored_element(
            tenant_context=tc, outcome_id=GET_A_JOB_OUTCOME_ID,
            element_kind="intermediary", element_id=APPLY_SCREEN_THROUGH_ID,
            label="Screen-through probability: fit times conversion likelihood",
            provenance_origin="llm_drafted", proof_state="pending",
            gate_id=APPLY_GATE_ID,
        )
        moved = await g.set_element_gate(
            tenant_context=tc, element_kind="lever",
            element_id=TAILORING_EFFORT_ID, gate_id=APPLY_GATE_ID,
        )
        await g.delete_authored_edge(
            tenant_context=tc, edge_type="FEEDS", source_kind="lever",
            source_id=TAILORING_EFFORT_ID, target_kind="intermediary",
            target_id=GOAL_WIN_PROBABILITY_ID,
        )
        await feeds("lever", TAILORING_EFFORT_ID, "intermediary",
                    APPLY_SCREEN_THROUGH_ID)
        log.info(
            "relocated Tailoring effort into Apply gate (moved=%s); "
            "goal edge migrated to Screen-through probability", moved,
        )
        for eid, label in APPLY_LEVERS:
            await merge_el("lever", eid, label, APPLY_GATE_ID)
            await feeds("lever", eid, "intermediary", APPLY_SCREEN_THROUGH_ID)
        for eid, label in APPLY_EXTERNALS:
            await merge_el("external", eid, label, APPLY_GATE_ID)
            await influences(eid, APPLY_SCREEN_THROUGH_ID)
        await feeds("intermediary", APPLY_SCREEN_THROUGH_ID, "gate", APPLY_GATE_ID)
        log.info(
            "Apply gate CDD: 4 levers (incl. relocated Tailoring), 1 intermediary, "
            "4 externals, wired -> gate",
        )

        # 3. Screening gate CDD.
        await merge_el("intermediary", SCREENING_CLEARING_ID,
                       "Probability of clearing to first interview",
                       SCREENING_GATE_ID)
        for eid, label in SCREENING_LEVERS:
            await merge_el("lever", eid, label, SCREENING_GATE_ID)
            await feeds("lever", eid, "intermediary", SCREENING_CLEARING_ID)
        for eid, label in SCREENING_EXTERNALS:
            await merge_el("external", eid, label, SCREENING_GATE_ID)
            await influences(eid, SCREENING_CLEARING_ID)
        await feeds("intermediary", SCREENING_CLEARING_ID, "gate",
                    SCREENING_GATE_ID)
        log.info(
            "Screening gate CDD: 3 levers, 1 intermediary, 3 externals, "
            "wired -> gate",
        )
        log.info("Apply + Screening gate CDDs authored from the framework (D207)")
    finally:
        await g.close()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.setLevel(logging.INFO)
    log.info("authoring the Apply + Screening gate CDDs (S103g)")
    asyncio.run(_seed())
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
