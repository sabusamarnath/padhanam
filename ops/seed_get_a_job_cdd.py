"""Author get-a-job's goal-level CDD from the job-search decision framework
(S103f, D206).

Slice one of the three-slice get-a-job framework build: the goal-level
portfolio-and-state CDD. Seeds get-a-job's authored CDD from
``charter/frameworks/job-search-decision-framework.md`` at the portfolio
altitude — one multi-objective outcome, the controllable portfolio levers, the
measured intermediaries, the uncontrolled externals — provenance ``llm_drafted``
/ ``pending`` (the framework is the draft; the operator's proof flips edited ones
to ``user_authored``). Applications and opportunities are Flow items per D198,
never levers; the per-gate process CDDs are slice two.

Invariant-4 discipline (no auto-deletion of user-authored content): the seed
**deletes only the ``llm_drafted`` generic drafts** (replacing a system draft is
the draft step of D200) and **preserves any ``user_authored`` element** from the
operator's prior proof passes. The delete skips the framework's own seeded ids,
so re-running is idempotent (it never deletes what it just seeded). Element
deletes remove the element node + its evidence edges only — the underlying work
units survive and re-bind on the next ``make correlate-units`` (D202).

Ops-only, composing the goal-graph port at the boundary (the ``seed_get_a_job``
precedent). Counts/ids only on the log (D21). Run inside ``padhanam-api`` via
``make seed-get-a-job-cdd``; then ``make correlate-units`` to bind units to the
authored elements.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from uuid import UUID

log = logging.getLogger("ops.seed_get_a_job_cdd")

# Personal dogfood tenant (ops/dogfood_provision.py); the get-a-job Outcome
# (ops/seed_get_a_job.py).
PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"
GET_A_JOB_OUTCOME_ID = UUID("00000000-0000-4000-8000-0000006300a1")

# The multi-objective outcome stance (framework §3 Role secured, §4 the goal is
# multi-objective). Scored on weighted axes; weights defined up front so Accept
# scores rather than guesses.
OUTCOME_STANCE = (
    "Role secured, scored on weighted axes: best-fit role, optionality, "
    "reputation with future colleagues, and relationships built. Weights are "
    "defined up front so the Accept decision scores rather than guesses."
)

# The controllable portfolio levers (framework §2, §3, §6, §7). Each is a
# (lever_id, label) pair; the label carries the framework name plus the key
# tokens the lexical matcher reads. The eighth (the origination fit rubric) is the
# S103t/D221 authored rule the operator proofs and scores leads against.
LEVERS: tuple[tuple[UUID, str], ...] = (
    (UUID("00000000-0000-4000-8000-00000063f001"),
     "Origination: open new processes via inbound brand and outbound outreach"),
    (UUID("00000000-0000-4000-8000-00000063f002"),
     "Targeting: choose segments, levels, companies and channel; warm over cold"),
    (UUID("00000000-0000-4000-8000-00000063f003"),
     "Tailoring effort: per-application investment, referrals, recruiter as advocate"),
    (UUID("00000000-0000-4000-8000-00000063f004"),
     "Leverage-building: competitive tension, a champion, a credible walk-away"),
    (UUID("00000000-0000-4000-8000-00000063f005"),
     "Synchronization: pace and bunch processes so offers land in one window"),
    (UUID("00000000-0000-4000-8000-00000063f006"),
     "Capacity allocation: kill weak processes, hold the portfolio budget"),
    (UUID("00000000-0000-4000-8000-00000063f007"),
     "Preparation by stage type: spend prep on discriminators and fit-and-sell rounds"),
    # The origination fit rubric (S103t, D221) — the authored rule behind
    # Origination + Targeting: which leads to originate and how to spend warm
    # access. A goal-level (portfolio) lever feeding Pipeline depth; the operator
    # proofs it live and sets fit_tier / warm_access_available per lead against it.
    (UUID("00000000-0000-4000-8000-00000063f008"),
     "Origination fit rubric — spend warm access on the highest tier (fit x warm). "
     "Tier 1 Bullseye: regulated enterprises building or buying agentic platforms "
     "where the build must be defensible under regulation (G-SIBs, large banks and "
     "insurers, regulated infrastructure); the load-bearing intersection is "
     "agentic-platform build meeting a regulated, audit-heavy buyer; BNY sits here. "
     "Tier 2 Strong: one axis fully present — regulated but not G-SIB, or an "
     "agentic-platform builder without the regulatory intensity. Tier 3 "
     "Opportunistic: real fit but neither the regulatory-defensibility edge nor the "
     "enterprise-procurement edge is load-bearing; apply when warm or when capacity "
     "is spare. Below tier: neither axis applies, do not originate. The "
     "fit-times-warm rule: Bullseye or Strong and warm apply now; Bullseye or "
     "Strong and cold build a warm path before applying (do not cold-apply a "
     "bullseye); Opportunistic and warm apply if capacity; Opportunistic and cold "
     "skip unless idle; Below tier skip."),
)

# The five measured intermediaries (framework §2, §4, §5) — positions, not
# controllable.
INTERMEDIARIES: tuple[tuple[UUID, str], ...] = (
    (UUID("00000000-0000-4000-8000-00000063f101"),
     "Pipeline depth: live processes against target depth"),
    (UUID("00000000-0000-4000-8000-00000063f102"),
     "Aggregate win-probability: the portfolio's offer likelihood, held as a band"),
    (UUID("00000000-0000-4000-8000-00000063f103"),
     "Accumulated leverage: built from the Apply stage onward, spent at Negotiate"),
    (UUID("00000000-0000-4000-8000-00000063f104"),
     "Accumulated information: band, criteria, decision-makers, unspoken concerns"),
    (UUID("00000000-0000-4000-8000-00000063f105"),
     "Offer synchronization: whether two or more offers mature in one window"),
)

# The five uncontrolled externals (framework §3, §4, §7).
EXTERNALS: tuple[tuple[UUID, str], ...] = (
    (UUID("00000000-0000-4000-8000-00000063f201"),
     "Labor-market demand and hiring concentration by sector"),
    (UUID("00000000-0000-4000-8000-00000063f202"),
     "Roles wired for an internal or referred candidate"),
    (UUID("00000000-0000-4000-8000-00000063f203"),
     "Mid-process hiring freeze or frozen budget"),
    (UUID("00000000-0000-4000-8000-00000063f204"),
     "Committee and debrief dynamics decided by people you never meet"),
    (UUID("00000000-0000-4000-8000-00000063f205"),
     "Champion turnover mid-process"),
)

# The authored causal structure (framework §1 levers -> intermediaries ->
# outcome; externals -> the position they move). Lever/intermediary FEEDS;
# external INFLUENCES (D198/D201 edge grammar). A default structure the operator
# refines in the proof pass. "Accumulated information" carries no incoming lever
# edge by design — it compounds from every interaction, not one lever — so it
# only FEEDS the outcome.
PIPELINE = INTERMEDIARIES[0][0]    # Pipeline depth
WINPROB = INTERMEDIARIES[1][0]     # Aggregate win-probability
LEVERAGE = INTERMEDIARIES[2][0]    # Accumulated leverage
OFFERSYNC = INTERMEDIARIES[4][0]   # Offer synchronization

LEVER_FEEDS: tuple[tuple[UUID, UUID], ...] = (
    (LEVERS[0][0], PIPELINE),     # Origination -> Pipeline depth
    (LEVERS[1][0], PIPELINE),     # Targeting -> Pipeline depth
    (LEVERS[2][0], WINPROB),      # Tailoring effort -> Aggregate win-probability
    (LEVERS[3][0], LEVERAGE),     # Leverage-building -> Accumulated leverage
    (LEVERS[4][0], OFFERSYNC),    # Synchronization -> Offer synchronization
    (LEVERS[5][0], PIPELINE),     # Capacity allocation -> Pipeline depth
    (LEVERS[6][0], WINPROB),      # Preparation by stage type -> Aggregate win-probability
    (LEVERS[7][0], PIPELINE),     # Origination fit rubric -> Pipeline depth (S103t, D221)
)
EXTERNAL_INFLUENCES: tuple[tuple[UUID, UUID], ...] = (
    (EXTERNALS[0][0], PIPELINE),   # Labor-market demand -> Pipeline depth
    (EXTERNALS[1][0], WINPROB),    # Roles wired internal -> Aggregate win-probability
    (EXTERNALS[2][0], PIPELINE),   # Hiring freeze -> Pipeline depth
    (EXTERNALS[3][0], WINPROB),    # Committee/debrief dynamics -> Aggregate win-probability
    (EXTERNALS[4][0], LEVERAGE),   # Champion turnover -> Accumulated leverage
)

# The framework's own seeded element ids — the delete pass skips these so a
# re-run never deletes what it just seeded (idempotent).
_FRAMEWORK_IDS = (
    {lid for lid, _ in LEVERS}
    | {iid for iid, _ in INTERMEDIARIES}
    | {eid for eid, _ in EXTERNALS}
)


async def _seed() -> None:
    from apps.cli._runtime import build_tenant_wiring
    from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
    from padhanam.config import Neo4jSettings

    wiring = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tc = wiring.tenant_context
    graph = Neo4jGraphRepository.from_settings(Neo4jSettings())
    try:
        # 1. Replace the generic LLM-drafted elements; preserve user_authored
        # (invariant 4). Skip the framework's own ids so re-runs are idempotent.
        current = await graph.read_authored_cdd(
            tenant_context=tc, outcome_id=GET_A_JOB_OUTCOME_ID
        )
        deleted = preserved = 0
        for el in current.elements:
            if el.element_id in _FRAMEWORK_IDS:
                continue
            if el.provenance_origin == "user_authored":
                preserved += 1
                log.info(
                    "preserving user_authored %s element %s (invariant 4)",
                    el.element_kind, el.element_id,
                )
                continue
            if el.provenance_origin == "llm_drafted":
                ok = await graph.delete_authored_element(
                    tenant_context=tc,
                    element_kind=el.element_kind,
                    element_id=el.element_id,
                )
                if ok:
                    deleted += 1
                    log.info(
                        "deleted llm_drafted %s element %s",
                        el.element_kind, el.element_id,
                    )
        log.info(
            "generic cleanup: %d llm_drafted deleted, %d user_authored preserved",
            deleted, preserved,
        )

        # 2. The multi-objective outcome stance (overwrites the llm_drafted one).
        await graph.set_authored_outcome(
            tenant_context=tc,
            outcome_id=GET_A_JOB_OUTCOME_ID,
            expected_outcome=OUTCOME_STANCE,
            provenance_origin="llm_drafted",
            proof_state="pending",
        )

        # 3. The framework elements (idempotent MERGE on the deterministic ids).
        for kind, elements in (
            ("lever", LEVERS),
            ("intermediary", INTERMEDIARIES),
            ("external", EXTERNALS),
        ):
            for element_id, label in elements:
                await graph.merge_authored_element(
                    tenant_context=tc,
                    outcome_id=GET_A_JOB_OUTCOME_ID,
                    element_kind=kind,
                    element_id=element_id,
                    label=label,
                    provenance_origin="llm_drafted",
                    proof_state="pending",
                )
        log.info(
            "seeded %d levers, %d intermediaries, %d externals (llm_drafted/pending)",
            len(LEVERS), len(INTERMEDIARIES), len(EXTERNALS),
        )

        # 4. The authored causal edges.
        for source_id, target_id in LEVER_FEEDS:
            await graph.merge_authored_edge(
                tenant_context=tc, edge_type="FEEDS",
                source_kind="lever", source_id=source_id,
                target_kind="intermediary", target_id=target_id,
            )
        for element_id, _ in INTERMEDIARIES:
            await graph.merge_authored_edge(
                tenant_context=tc, edge_type="FEEDS",
                source_kind="intermediary", source_id=element_id,
                target_kind="outcome", target_id=GET_A_JOB_OUTCOME_ID,
            )
        for source_id, target_id in EXTERNAL_INFLUENCES:
            await graph.merge_authored_edge(
                tenant_context=tc, edge_type="INFLUENCES",
                source_kind="external", source_id=source_id,
                target_kind="intermediary", target_id=target_id,
            )
        log.info(
            "wired %d lever->intermediary FEEDS, %d intermediary->outcome FEEDS, "
            "%d external->intermediary INFLUENCES",
            len(LEVER_FEEDS), len(INTERMEDIARIES), len(EXTERNAL_INFLUENCES),
        )
        log.info("get-a-job goal-level CDD authored from the framework (D206)")
    finally:
        await graph.close()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.setLevel(logging.INFO)
    log.info("authoring get-a-job's goal-level CDD from the framework (S103f)")
    asyncio.run(_seed())
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
