"""Instantiate the operator-confirmed get-a-job opportunities (S103h, D208).

Slice two-B: an opportunity is a Flow item (D198). This instantiates the three
operator-confirmed opportunities from the densest live clusters, attaches their
units by an auditable company signature, and positions each at its
furthest-evidenced gate.

The three (operator-confirmed this session, spanning the gate range):
  - Acme            — interview stage; signature acme.example OR (screenloop.com
                       AND the subject names Acme — the guarded two-domain form,
                       since Screenloop is a multi-company interview tool).
  - Globex Legal    — application stage; signature globex-legal.example.
  - Initech AI   — mid-process; signature initech-ai.example.

provenance_origin=user_authored (the operator confirmed these are real),
proof_state=pending (the position + membership await the operator's surface
proof). current_gate_id is the furthest gate (by gate_order) the opportunity's
units evidence among the live gates (Apply, Screening) — the interview gate is
two-C, so an interview-stage opportunity is capped at the furthest of these two.

Idempotent (clear-then-attach + MERGE). Ops-only, counts/ids on the log (D21).
Run inside padhanam-api via make instantiate-opportunities; then
make correlate-units (the binds read per opportunity via BELONGS_TO).
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections import defaultdict
from uuid import UUID

log = logging.getLogger("ops.instantiate_get_a_job_opportunities")

PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"
GET_A_JOB_OUTCOME_ID = UUID("00000000-0000-4000-8000-0000006300a1")
FREE = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com",
        "yahoo.com", "icloud.com", "me.com"}

ACME = UUID("00000000-0000-4000-8000-0000063b0001")
GLOBEX = UUID("00000000-0000-4000-8000-0000063b0002")
INITECH = UUID("00000000-0000-4000-8000-0000063b0003")

OPPORTUNITIES = (
    (ACME, "Acme", "acme.example / screenloop.com+Acme"),
    (GLOBEX, "Globex Legal", "globex-legal.example"),
    (INITECH, "Initech AI", "initech-ai.example"),
)


def _company(frm, tos):
    for a in [frm or ""] + list(tos or []):
        a = (a or "").lower()
        if "@" in a:
            dom = a.split("@")[-1].strip(">").strip()
            if dom and dom not in FREE:
                return dom
    return None


def _match(company, subject):
    """Map an email's (company domain, subject) to an opportunity id, or None.
    Acme uses the guarded two-domain signature (screenloop.com only when the
    subject names Acme)."""
    s = (subject or "").lower()
    if company == "acme.example":
        return ACME
    if company == "screenloop.com" and "acme" in s:
        return ACME
    if company == "globex-legal.example":
        return GLOBEX
    if company == "initech-ai.example":
        return INITECH
    return None


async def _run() -> None:
    from apps.cli._runtime import build_tenant_wiring
    from contexts.email.adapters.outbound.postgres.email_store import (
        PostgresEmailStore,
    )
    from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
    from padhanam.config import Neo4jSettings
    from shared_kernel import TenantId

    w = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tc = w.tenant_context
    sf = w.session_factory

    async def _resolver(_tid):
        return sf

    g = Neo4jGraphRepository.from_settings(Neo4jSettings())
    try:
        # Email meta keyed by email id (= the email facet_id).
        store = PostgresEmailStore(
            per_tenant_sessionmaker_resolver=_resolver,
            bound_tenant_id=TenantId(str(tc.tenant_id)),
        )
        emails = await store.list_emails(tenant_context=tc)
        meta = {e.id: (_company(e.from_address, e.to_addresses), e.subject)
                for e in emails}

        # get-a-job bound units (any element/gate/outcome) + their email facets.
        ev = await g.list_element_evidence(tenant_context=tc)
        gaj_units = {e.unit_id for e in ev if e.outcome_id == GET_A_JOB_OUTCOME_ID}
        recs = await g.list_units(tenant_context=tc)
        unit_opp: dict[UUID, UUID] = {}
        for r in recs:
            if r.unit_id not in gaj_units:
                continue
            for f in r.links:
                if not str(f.facet_type).lower().endswith("email"):
                    continue
                m = meta.get(f.facet_id)
                if not m:
                    continue
                opp = _match(m[0], m[1])
                if opp is not None:
                    unit_opp[r.unit_id] = opp  # one opportunity per unit (first match)
        members = defaultdict(set)
        for uid, opp in unit_opp.items():
            members[opp].add(uid)

        # Gate order map for the furthest-evidenced-gate position.
        gates = await g.list_gates(tenant_context=tc, outcome_id=GET_A_JOB_OUTCOME_ID)
        gate_order = {ga.gate_id: ga.gate_order for ga in gates}
        # Each unit's evidenced gates (from element evidence).
        unit_gates = defaultdict(set)
        for e in ev:
            if e.gate_id is not None:
                unit_gates[e.unit_id].add(e.gate_id)

        for opp_id, name, sig in OPPORTUNITIES:
            unit_ids = members.get(opp_id, set())
            # Furthest gate (max gate_order) any member unit evidences.
            evidenced = {gid for uid in unit_ids for gid in unit_gates.get(uid, ())}
            current_gate = None
            if evidenced:
                current_gate = max(evidenced, key=lambda gid: gate_order.get(gid, -1))
            await g.merge_opportunity(
                tenant_context=tc, opportunity_id=opp_id,
                outcome_id=GET_A_JOB_OUTCOME_ID, name=name,
                current_gate_id=current_gate,
                provenance_origin="user_authored", proof_state="pending",
                source=sig,
            )
            await g.clear_opportunity_units(tenant_context=tc, opportunity_id=opp_id)
            for uid in unit_ids:
                await g.attach_unit_to_opportunity(
                    tenant_context=tc, unit_id=uid, opportunity_id=opp_id
                )
            gname = next((ga.name for ga in gates if ga.gate_id == current_gate),
                         "(none)")
            log.info(
                "instantiated %s (%s): %d units, current gate = %s",
                name, sig, len(unit_ids), gname,
            )
        log.info("instantiated %d operator-confirmed opportunities (D208)",
                 len(OPPORTUNITIES))
    finally:
        await g.close()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.setLevel(logging.INFO)
    log.info("instantiating the operator-confirmed get-a-job opportunities (S103h)")
    asyncio.run(_run())
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
