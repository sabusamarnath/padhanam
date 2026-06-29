"""Content-extraction clustering (S103o, D215): extract company/role from the
unclustered bound units, group multi-touch threads, classify live/closed, and
instantiate them system-suggested for the operator to proof.

Operator-gated, like correlate_units / instantiate_get_a_job_opportunities. The
LLM extraction runs behind the structured-output seam (the LiteLLMAdapter, D16) on
read-only ingested content (§9); the clustering + classification are the pure
domain (opportunity_extraction). Re-runnable: opportunity ids are deterministic
(uuid5 of the signature), so a re-run reconciles the same clusters.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID, uuid5

log = logging.getLogger("ops.cluster_opportunities")

PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"
GET_A_JOB_OUTCOME_ID = UUID("00000000-0000-4000-8000-0000006300a1")
# Stable namespace so a cluster's signature maps to the same opportunity id each run.
_OPP_NS = UUID("00000000-0000-4000-8000-00000c150000")
_BATCH = 15


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


async def _run() -> None:
    from apps.cli._runtime import build_tenant_wiring
    from contexts.daily_driver.domain.opportunity_extraction import (
        EXTRACTION_SCHEMA,
        build_extraction_prompt,
        cluster_and_classify,
        parse_extraction,
    )
    from contexts.email.adapters.outbound.postgres.email_store import (
        PostgresEmailStore,
    )
    from contexts.inference.adapters.outbound.litellm import LiteLLMAdapter
    from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
    from padhanam.config import Neo4jSettings
    from padhanam.config.inference import InferenceSettings
    from shared_kernel import TenantId
    from shared_kernel.structured_output import (
        StructuredOutputParseFailure,
        StructuredOutputRequest,
    )

    w = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tc = w.tenant_context
    sf = w.session_factory

    async def _resolver(_tid):
        return sf

    g = Neo4jGraphRepository.from_settings(Neo4jSettings())
    inference = LiteLLMAdapter(settings=InferenceSettings())
    try:
        store = PostgresEmailStore(
            per_tenant_sessionmaker_resolver=_resolver,
            bound_tenant_id=TenantId(str(tc.tenant_id)),
        )
        emails = await store.list_emails(tenant_context=tc)
        content = {e.id: (e.subject or "", e.body or "", e.received_at) for e in emails}

        # get-a-job bound units, minus those already in an opportunity (the lens's
        # unclustered set). Routed pipeline/market units are not bound (S103i dropped
        # them), so they are already out — the counts are untouched by construction.
        ev = await g.list_element_evidence(tenant_context=tc)
        bound = {e.unit_id for e in ev if e.outcome_id == GET_A_JOB_OUTCOME_ID}
        clustered = set(await g.list_clustered_unit_ids(tenant_context=tc))
        unclustered = bound - clustered

        # Each unclustered unit's email facet content + its latest touch (received_at).
        recs = await g.list_units(tenant_context=tc)
        items: list[tuple[UUID, str, str]] = []
        latest_by_unit: dict[UUID, datetime] = {}
        for r in recs:
            if r.unit_id not in unclustered:
                continue
            for f in r.links:
                if not str(f.facet_type).lower().endswith("email"):
                    continue
                c = content.get(f.facet_id)
                if not c:
                    continue
                items.append((r.unit_id, c[0], c[1]))
                if c[2] is not None:
                    prev = latest_by_unit.get(r.unit_id)
                    if prev is None or c[2] > prev:
                        latest_by_unit[r.unit_id] = c[2]
                break  # one email facet per unit is enough to extract
        log.info("unclustered bound units with email content: %d", len(items))

        # Extract company/role/signal via the LLM, batched.
        extractions = []
        for ci, chunk in enumerate(_chunks(items, _BATCH)):
            unit_ids = tuple(u for u, _, _ in chunk)
            prompt_items = tuple((s, b) for _, s, b in chunk)
            req = StructuredOutputRequest(
                prompt=build_extraction_prompt(prompt_items), schema=EXTRACTION_SCHEMA
            )
            try:
                resp = await inference.generate_structured(req)
            except StructuredOutputParseFailure:
                log.warning("batch %d: no schema-conforming extraction, skipped", ci)
                continue
            batch = parse_extraction(resp.value, unit_ids)
            extractions.extend(batch)
            log.info("batch %d: %d/%d extracted", ci, len(batch), len(chunk))

        now = datetime.now(timezone.utc)
        candidates = cluster_and_classify(
            tuple(extractions), latest_by_unit=latest_by_unit, now=now
        )

        # Furthest gate per cluster (max gate_order any member unit evidences).
        gates = await g.list_gates(tenant_context=tc, outcome_id=GET_A_JOB_OUTCOME_ID)
        gate_order = {ga.gate_id: ga.gate_order for ga in gates}
        unit_gates = defaultdict(set)
        for e in ev:
            if e.gate_id is not None:
                unit_gates[e.unit_id].add(e.gate_id)

        live_n = closed_n = 0
        for c in candidates:
            opp_id = uuid5(_OPP_NS, f"{c.company.lower()}|{c.role.lower()}")
            evidenced = {gid for uid in c.unit_ids for gid in unit_gates.get(uid, ())}
            current_gate = (
                max(evidenced, key=lambda gid: gate_order.get(gid, -1))
                if evidenced else None
            )
            await g.merge_opportunity(
                tenant_context=tc, opportunity_id=opp_id,
                outcome_id=GET_A_JOB_OUTCOME_ID, name=c.name,
                current_gate_id=current_gate,
                provenance_origin="system_suggested", proof_state="pending",
                source=f"{c.company}|{c.role}",
            )
            await g.clear_opportunity_units(tenant_context=tc, opportunity_id=opp_id)
            for uid in c.unit_ids:
                await g.attach_unit_to_opportunity(
                    tenant_context=tc, unit_id=uid, opportunity_id=opp_id
                )
            if c.status == "closed" and c.closed_reason:
                await g.close_opportunity(
                    tenant_context=tc, opportunity_id=opp_id,
                    closed_reason=c.closed_reason,
                )
                closed_n += 1
            else:
                live_n += 1
            log.info(
                "  %s [%s%s]: %d units, gate=%s",
                c.name, c.status,
                f"/{c.closed_reason}" if c.closed_reason else "",
                len(c.unit_ids),
                next((ga.name for ga in gates if ga.gate_id == current_gate), "(none)"),
            )

        clustered_units = sum(len(c.unit_ids) for c in candidates)
        log.info(
            "S103o re-measure: %d candidate opportunities (%d live, %d closed) from "
            "%d unclustered units; %d units clustered, %d remain unclustered",
            len(candidates), live_n, closed_n, len(items),
            clustered_units, len(items) - clustered_units,
        )
    finally:
        await g.close()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.setLevel(logging.INFO)
    log.info("content-extraction clustering of the unclustered bound units (S103o)")
    asyncio.run(_run())
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
