"""S100 — ground-truth sampler for the unlinked-email residual (D174 tier-three call).

The D174 tier-three (embedding) decision hinges on the missed-link rate of the
email residual — the folded-dominant unlinked class (169 rows) that cannot be
sized by embedding reuse (``email_chunks`` is empty: the live emails arrived via
the scoped ``sync_email_jobsearch`` path, which never ran ``index_email``). The
honest instrument is operator ground truth, not an embedding proxy that would
validate itself (the S91 operator-as-oracle pattern).

This script draws a representative sample of the unlinked-email residual and
writes the subjects to a **local, uncommitted** file for the operator to tag
into genuine-orphan / missed-link / latent-goal. The script carries no content
(D21); the output file holds the operator's own email subjects and is written
**outside the repo** (``/tmp``) — never committed, never logged. Stdout is
counts and the file path only.

Run in the api container (it has the decryption key path + store wiring):
    docker cp ops/s100_sample_email_residual.py <api>:/tmp/ && \
    docker exec <api> python /tmp/s100_sample_email_residual.py

Read-only: no graph write, no matcher run-path change. Not imported by anything.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from shared_kernel.authorisation import (
    ROLE_OPERATOR,
    authorisations_for_roles,
)

# Personal dogfood tenant (ops/dogfood_provision.py).
PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"

# Local, uncommitted output — outside the repo, operator's own content (D21).
_OUT_PATH = "/tmp/s100_email_sample.tsv"
_SAMPLE_SIZE = 40

log = logging.getLogger("ops.s100_sample_email_residual")


async def _sample() -> None:
    from apps.api._daily_driver_wiring import UnitGraphAdapter
    from apps.cli._runtime import build_tenant_wiring
    from contexts.daily_driver.domain.work_unit import FacetType
    from contexts.email.adapters.outbound.postgres.email_store import (
        PostgresEmailStore,
    )
    from contexts.ingestion.adapters.outbound.neo4j import (
        Neo4jGraphRepository,
    )
    from padhanam.config import Neo4jSettings
    from shared_kernel import TenantContext, TenantId

    wiring = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tenant_context: TenantContext = wiring.tenant_context
    session_factory = wiring.session_factory

    async def _resolver(_tid: TenantId):
        return session_factory

    graph = Neo4jGraphRepository.from_settings(Neo4jSettings())
    unit_graph = UnitGraphAdapter(unit_graph=graph)

    # Unlinked units = units with no goal (SERVES) edge; keep their email facets.
    records = await unit_graph.list_units(tenant_context=tenant_context)
    edges = await unit_graph.list_goal_edges(tenant_context=tenant_context)
    served = {e.unit_id for e in edges}

    unlinked_email_ids: list = []
    for rec in records:
        if rec.unit_id in served:
            continue
        for facet in rec.facets:
            if facet.facet_type is FacetType.EMAIL:
                unlinked_email_ids.append(facet.facet_id)
    unlinked_email_ids = sorted(set(unlinked_email_ids), key=str)

    # Decrypted subjects, keyed by email id (= the email facet_id).
    store = PostgresEmailStore(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=TenantId(str(tenant_context.tenant_id)),
    )
    emails = await store.list_emails(tenant_context=tenant_context)
    subject_by_id = {e.id: (e.subject or "(no subject)") for e in emails}

    # Representative sample: even stride across the sorted residual (deterministic).
    total = len(unlinked_email_ids)
    if total == 0:
        print("S100 sampler: 0 unlinked email units found — nothing to sample.")
        return
    step = max(1, total // _SAMPLE_SIZE)
    sampled = unlinked_email_ids[::step][:_SAMPLE_SIZE]

    matched = sum(1 for eid in sampled if eid in subject_by_id)
    with open(_OUT_PATH, "w", encoding="utf-8") as fh:
        fh.write(
            "# S100 email-residual ground-truth sample. Tag each row in the TAG "
            "column:\n"
            "#   G = genuine-orphan (serves none of the 8 seeded goals)\n"
            "#   M = missed-link (relates to a seeded goal; the matcher missed "
            "it)\n"
            "#   L = latent-goal (coherent work serving an UNseeded goal)\n"
            "# Then save. This file is local-only; nothing here enters the repo "
            "or log.\n"
            "# idx\tTAG\temail_id\tsubject\n"
        )
        for i, eid in enumerate(sampled, start=1):
            subject = subject_by_id.get(eid, "(subject not found)")
            subject = " ".join(str(subject).split())  # single line
            fh.write(f"{i}\t?\t{eid}\t{subject}\n")

    # Counts only to stdout — no content.
    print(
        "S100 sampler complete:\n"
        f"  unlinked email units (residual total): {total}\n"
        f"  sampled (even stride, step={step}): {len(sampled)}\n"
        f"  subjects resolved for sample: {matched}/{len(sampled)}\n"
        f"  tagging file written: {_OUT_PATH}\n"
        "  (local-only; tag the TAG column G/M/L and hand back the counts)"
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_sample())
    return 0


if __name__ == "__main__":
    sys.exit(main())
