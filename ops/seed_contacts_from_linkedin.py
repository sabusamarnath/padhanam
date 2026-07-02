"""Seed system-suggested :Contact nodes from the LinkedIn self-export (S103v, D223).

The LinkedIn arm of the contact graph (D223). Reads the member's self-export archive
(a zip or an unzipped directory) via the built ``SelfExportArchiveSource``, and seeds
each distinct person as a ``system_suggested`` :Contact via the S103u ``merge_contact``
(``capture_source`` = ``linkedin``), for the operator to proof — the same loop the
email seed feeds. Connections carry ``degree`` = ``first`` and the real company from
the export column (no extraction); message senders carry no company (the operator
adds it in proof).

Dedup: against the email-seeded contacts and within the archive, on the normalized
(name, company) signature, with a **name-only fallback** for the company-less message
senders. On a match the person is **skipped** — their existing ``contact_id`` and any
proof work are preserved (one person is one node). New people get a deterministic
``uuid5`` id, so a re-run is idempotent.

Read-only on the archive; no write to any LinkedIn surface; no vendor SDK (the parse
is stdlib, behind the port). Ops-only, counts on the log (D21). The archive is the
operator's file, so this runs as the operator's gated pass:
``docker compose cp <archive> padhanam-api:/tmp/linkedin`` then
``make seed-contacts-linkedin FILE=/tmp/linkedin``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from uuid import NAMESPACE_URL, uuid5

log = logging.getLogger("ops.seed_contacts_from_linkedin")

PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"


def _norm_name(name: str | None) -> str:
    return " ".join((name or "").strip().lower().split())


def _archive_path() -> str:
    path = (sys.argv[1] if len(sys.argv) > 1 else "") or os.environ.get("FILE", "")
    if not path:
        raise SystemExit(
            "usage: python -m ops.seed_contacts_from_linkedin <archive-path> "
            "(or FILE=<path>); the archive is the LinkedIn self-export zip or dir"
        )
    return path


async def _run(path: str) -> None:
    from apps.cli._runtime import build_tenant_wiring
    from contexts.daily_driver.domain.contacts import normalize_company
    from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
    from ops.linkedin_archive_source import SelfExportArchiveSource
    from padhanam.config import Neo4jSettings

    w = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tc = w.tenant_context
    g = Neo4jGraphRepository.from_settings(Neo4jSettings())
    try:
        parsed = SelfExportArchiveSource(path).load()
        connections = [c for c in parsed if c.kind == "connection"]
        messages = [c for c in parsed if c.kind == "message"]
        log.info(
            "parsed archive %s: %d connections, %d distinct message senders",
            path, len(connections), len(messages),
        )

        existing = await g.list_contacts(tenant_context=tc)
        by_sig: dict[str, str] = {}
        by_name: dict[str, str] = {}
        for c in existing:
            n = _norm_name(c.name)
            by_sig[f"{n}|{normalize_company(c.company)}"] = str(c.contact_id)
            by_name.setdefault(n, str(c.contact_id))

        seeded = deduped = 0
        for lc in parsed:
            n = _norm_name(lc.name)
            if not n:
                continue
            sig = f"{n}|{normalize_company(lc.company)}"
            if sig in by_sig or n in by_name:
                deduped += 1
                continue
            cid = uuid5(NAMESPACE_URL, f"contact:{tc.tenant_id}:linkedin:{sig}")
            await g.merge_contact(
                tenant_context=tc, contact_id=cid, name=lc.name, email=None,
                company=lc.company, degree=lc.degree, strength=None,
                reachability=None, capture_source="linkedin",
                provenance_origin="system_suggested",
            )
            by_sig[sig] = str(cid)
            by_name.setdefault(n, str(cid))
            seeded += 1

        log.info(
            "seeded %d system_suggested LinkedIn contacts; %d deduped against "
            "existing (email + within-archive) — the operator proofs "
            "degree/strength/reachability (D222)", seeded, deduped,
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
    path = _archive_path()
    log.info("seeding contacts from the LinkedIn self-export (S103v, D223)")
    asyncio.run(_run(path))
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
