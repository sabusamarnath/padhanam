"""Split get-a-job's single bundled outcome into the measurable-outcome layer (S103k, D211).

The proof pass caught a frame error: slice one bundled the measurable results into a
single "Role secured" stance on the goal node, and — because the model had no outcome
layer at all — the intermediaries fed the goal directly and read as endpoints. This
introduces the layer:

  1. Author the five measurable outcomes as :MeasurableOutcome nodes (llm_drafted).
  2. Re-point every goal-level intermediary->goal FEEDS edge onto the outcomes (the
     5 framework intermediaries per the wiring map; the 2 user_authored ones
     ["Initial Interview invitations", "2nd stage interviews"] -> Offer received, so
     no intermediary is left feeding the goal directly; their nodes/labels/type are
     preserved, only the downstream edge moves — invariant 4 protects content).
  3. Tie the five outcomes to the goal (outcome -> :Outcome FEEDS).
  4. Repurpose the goal stance from the bundle to the goal statement.

Idempotent: MERGE re-creates nodes/edges, the delete no-ops once re-pointed, and the
stance overwrite is stable. Run after migration 0009.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from uuid import UUID

log = logging.getLogger("ops.split_outcome")

PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"

GET_A_JOB_OUTCOME_ID = UUID("00000000-0000-4000-8000-0000006300a1")

# The goal statement (the right edge), repurposed from the bundled "Role secured"
# stance; the bundle's measurable content now lives in the five outcome nodes below.
GOAL_STANCE = (
    "Secure a great-fit role — the weighted result across the five measurable "
    "outcomes (offer received, offer quality, optionality, reputation, relationships)."
)

# The five measurable outcomes (framework §3 Role secured, §4 the multi-objective
# goal). Labels carry a short name before the colon (the render shows the head).
OUT_OFFER = UUID("00000000-0000-4000-8000-00000063f301")
OUT_QUALITY = UUID("00000000-0000-4000-8000-00000063f302")
OUT_OPTION = UUID("00000000-0000-4000-8000-00000063f303")
OUT_REPUTATION = UUID("00000000-0000-4000-8000-00000063f304")
OUT_RELATIONSHIPS = UUID("00000000-0000-4000-8000-00000063f305")

OUTCOMES: tuple[tuple[UUID, str], ...] = (
    (OUT_OFFER, "Offer received: a real offer in hand"),
    (OUT_QUALITY, "Offer quality and comp: band, level, terms"),
    (OUT_OPTION,
     "Optionality: competing live offers and walk-away strength at decision time"),
    (OUT_REPUTATION,
     "Reputation with future colleagues: how the process left you seen"),
    (OUT_RELATIONSHIPS,
     "Relationships built: durable contacts the search created"),
)

# The framework intermediaries (deterministic ids from seed_get_a_job_cdd).
INT_PIPELINE = UUID("00000000-0000-4000-8000-00000063f101")
INT_WINPROB = UUID("00000000-0000-4000-8000-00000063f102")
INT_LEVERAGE = UUID("00000000-0000-4000-8000-00000063f103")
INT_INFO = UUID("00000000-0000-4000-8000-00000063f104")
INT_OFFERSYNC = UUID("00000000-0000-4000-8000-00000063f105")

# The intermediary -> outcome wiring (the operator proofs these edges). Every
# intermediary feeds >=1 outcome and every outcome has >=1 feeder. Beyond the brief's
# illustrative list this adds Offer-synchronization -> Optionality (synchronized
# offers are what *create* optionality) and Accumulated-information -> Reputation
# (depth of engagement shapes how you are seen) — both flagged as proof candidates,
# Reputation's feeder being the weakest link.
INT_FEEDS_OUTCOME: tuple[tuple[UUID, UUID], ...] = (
    (INT_PIPELINE, OUT_OFFER),
    (INT_WINPROB, OUT_OFFER),
    (INT_WINPROB, OUT_QUALITY),
    (INT_LEVERAGE, OUT_QUALITY),
    (INT_LEVERAGE, OUT_OPTION),
    (INT_OFFERSYNC, OUT_OPTION),
    (INT_INFO, OUT_QUALITY),
    (INT_INFO, OUT_RELATIONSHIPS),
    (INT_INFO, OUT_REPUTATION),
)


async def _run() -> None:
    from apps.cli._runtime import build_tenant_wiring
    from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
    from padhanam.config import Neo4jSettings

    wiring = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tc = wiring.tenant_context
    graph = Neo4jGraphRepository.from_settings(Neo4jSettings())
    try:
        before = await graph.read_authored_cdd(
            tenant_context=tc, outcome_id=GET_A_JOB_OUTCOME_ID
        )

        # 1. Author the five measurable outcomes (llm_drafted/pending; the operator
        # proofs). MERGE is idempotent on the deterministic ids.
        for element_id, label in OUTCOMES:
            await graph.merge_authored_element(
                tenant_context=tc,
                outcome_id=GET_A_JOB_OUTCOME_ID,
                element_kind="measurable_outcome",
                element_id=element_id,
                label=label,
                provenance_origin="llm_drafted",
                proof_state="pending",
            )
        log.info("authored %d measurable outcomes (llm_drafted/pending)", len(OUTCOMES))

        # 2. Re-point: delete every goal-level edge feeding the goal :Outcome from a
        # lever/intermediary/external source (measurable_outcome->goal edges are kept
        # so a re-run is a no-op). This is what removes the intermediaries from the
        # outcome position; the source nodes survive (only the edge is deleted).
        repointed = []
        for ed in before.edges:
            if (
                str(ed.target_id) == str(GET_A_JOB_OUTCOME_ID)
                and ed.target_kind == "outcome"
                and ed.source_kind in {"lever", "intermediary", "external"}
            ):
                await graph.delete_authored_edge(
                    tenant_context=tc,
                    edge_type=ed.edge_type,
                    source_kind=ed.source_kind,
                    source_id=ed.source_id,
                    target_kind="outcome",
                    target_id=GET_A_JOB_OUTCOME_ID,
                )
                repointed.append((ed.source_kind, ed.source_id))
        log.info("deleted %d direct ->goal edges (re-pointing onto outcomes)", len(repointed))

        # 3. Wire the framework intermediaries -> outcomes per the map.
        for source_id, target_id in INT_FEEDS_OUTCOME:
            await graph.merge_authored_edge(
                tenant_context=tc, edge_type="FEEDS",
                source_kind="intermediary", source_id=source_id,
                target_kind="measurable_outcome", target_id=target_id,
            )

        # 4. The 2 user_authored goal-level intermediaries -> Offer received (their
        # nodes/labels/type preserved; flagged as proof candidates). Identified from
        # the live read so the op carries no hardcoded user ids.
        framework_ints = {
            INT_PIPELINE, INT_WINPROB, INT_LEVERAGE, INT_INFO, INT_OFFERSYNC,
        }
        user_ints = [
            e for e in before.elements
            if e.element_kind == "intermediary"
            and e.gate_id is None
            and e.element_id not in framework_ints
        ]
        for e in user_ints:
            await graph.merge_authored_edge(
                tenant_context=tc, edge_type="FEEDS",
                source_kind="intermediary", source_id=e.element_id,
                target_kind="measurable_outcome", target_id=OUT_OFFER,
            )
            log.info(
                "re-pointed user_authored intermediary %s (%r) -> Offer received "
                "[proof candidate]", e.element_id, e.label,
            )

        # 5. Tie the five outcomes to the goal.
        for element_id, _ in OUTCOMES:
            await graph.merge_authored_edge(
                tenant_context=tc, edge_type="FEEDS",
                source_kind="measurable_outcome", source_id=element_id,
                target_kind="outcome", target_id=GET_A_JOB_OUTCOME_ID,
            )
        log.info(
            "wired %d intermediary->outcome + %d user->outcome + %d outcome->goal edges",
            len(INT_FEEDS_OUTCOME), len(user_ints), len(OUTCOMES),
        )

        # 6. Repurpose the goal stance from the bundle to the goal statement. "Role
        # secured" was llm_drafted (no invariant-4 concern); its measurable content
        # carries forward into the five outcome nodes.
        await graph.set_authored_outcome(
            tenant_context=tc,
            outcome_id=GET_A_JOB_OUTCOME_ID,
            expected_outcome=GOAL_STANCE,
            provenance_origin="llm_drafted",
            proof_state="pending",
        )
        log.info("repurposed the goal stance to the goal statement (D211)")
    finally:
        await graph.close()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.setLevel(logging.INFO)
    log.info("splitting get-a-job's bundled outcome into measurable outcomes (S103k)")
    asyncio.run(_run())
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
