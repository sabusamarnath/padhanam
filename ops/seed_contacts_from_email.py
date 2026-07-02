"""Seed system-suggested :Contact nodes from the moat senders (S103u, D222).

The contact graph behind warm access (D222). Reads the senders of the **confirmed
job-search emails** (the moat, D183/D184) and instantiates each distinct real-person
sender as a ``system_suggested`` :Contact linked to its company, for the operator to
proof (confirm / enrich degree·strength·reachability / reject) and to back a lead's
derived warm access.

Read-only on the email store (D21/D148/D151 — extraction never fetches or writes).
This mirrors ``instantiate_get_a_job_opportunities`` (which reads the same store via
``PostgresEmailStore.list_emails().from_address``); ``list_confirmed()`` /
``get_email_content(facet_id).sender`` are the daily-driver *port* wrappers over the
identical reads — ``list_job_search_classifications`` is what ``list_confirmed``
returns, and ``from_address`` is the ``sender`` field. Using the store directly is
the established ops idiom.

Filtering (D222, precision.py): a sender is kept only when its domain is a **real
company domain** — not a board (LinkedIn/Indeed), an ATS (Ashby/Workday), a free
provider (gmail/outlook), or an automated/no-reply local part. Those are systems and
job boards, not people in the operator's network; a free-domain recruiter the
operator knows is added by hand (``capture_source = manual``). Company is derived
from the domain (title-cased second-level label) for the operator to correct.

Idempotent: ``contact_id`` is a deterministic uuid5 of (tenant, email), so a re-run
merges the same node. Ops-only, counts/ids on the log (D21). Run inside padhanam-api
via ``make seed-contacts``.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from uuid import NAMESPACE_URL, UUID, uuid5

log = logging.getLogger("ops.seed_contacts_from_email")

PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"

# Automated / role local-parts that are not a person (kept minimal — the operator
# rejects anything else that is not a real contact in the proof pass).
_NOREPLY_LOCALPARTS = frozenset({
    "no-reply", "noreply", "no_reply", "donotreply", "do-not-reply", "do_not_reply",
    "notifications", "notification", "mailer-daemon", "postmaster", "bounce",
    "bounces", "auto", "automated", "alerts", "alert",
})
# Compound public suffixes so the company label is parts[-3], not parts[-2].
_COMPOUND_TLDS = frozenset({"co.uk", "com.au", "co.nz", "com.br", "co.za", "co.in"})


def _parse_sender(from_address: str | None) -> tuple[str, str, str] | None:
    """(display_name, email, domain) from a From header, or None if unparseable.
    Handles ``Name <email>`` and bare ``email``."""
    raw = (from_address or "").strip()
    if not raw or "@" not in raw:
        return None
    name = ""
    addr = raw
    if "<" in raw and ">" in raw:
        name = raw.split("<", 1)[0].strip().strip('"').strip()
        addr = raw.split("<", 1)[1].split(">", 1)[0].strip()
    addr = addr.lower().strip()
    if "@" not in addr:
        return None
    local, domain = addr.rsplit("@", 1)
    domain = domain.strip().strip(">").strip()
    if not domain or not local:
        return None
    if not name:
        # Derive a name from the local part ("jane.doe" -> "Jane Doe").
        name = local.replace(".", " ").replace("_", " ").replace("-", " ").title()
    return name, addr, domain


def _company_from_domain(domain: str) -> str:
    """Title-cased company from a real domain ("globex-legal.example" -> "Globex
    Legal"). A default the operator corrects in proof (D200)."""
    parts = domain.split(".")
    last2 = ".".join(parts[-2:]) if len(parts) >= 2 else ""
    sld = parts[-3] if last2 in _COMPOUND_TLDS and len(parts) >= 3 else (
        parts[-2] if len(parts) >= 2 else parts[0]
    )
    return " ".join(w.title() for w in sld.replace("-", " ").split())


async def _run() -> None:
    from apps.cli._runtime import build_tenant_wiring
    from contexts.daily_driver.domain.precision import (
        ATS_DOMAINS,
        BOARD_DOMAINS,
        FREE_DOMAINS,
    )
    from contexts.email.adapters.outbound.postgres.email_store import (
        PostgresEmailStore,
    )
    from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
    from padhanam.config import Neo4jSettings
    from shared_kernel import TenantId

    system_domains = BOARD_DOMAINS | ATS_DOMAINS | FREE_DOMAINS

    w = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tc = w.tenant_context
    sf = w.session_factory

    async def _resolver(_tid):
        return sf

    g = Neo4jGraphRepository.from_settings(Neo4jSettings())
    try:
        store = PostgresEmailStore(
            per_tenant_sessionmaker_resolver=_resolver,
            bound_tenant_id=TenantId(str(tc.tenant_id)),
        )
        # The moat: the confirmed job-search emails (what list_confirmed wraps).
        confirmed = await store.list_job_search_classifications(tenant_context=tc)
        confirmed_ids = {fid for fid, _kind, _rec in confirmed}
        emails = await store.list_emails(tenant_context=tc)

        # Distinct real-person senders across the confirmed emails, deduped by email.
        by_email: dict[str, tuple[str, str]] = {}  # email -> (name, domain)
        seen = filtered_system = filtered_noreply = 0
        for e in emails:
            if e.id not in confirmed_ids:
                continue
            seen += 1
            parsed = _parse_sender(e.from_address)
            if parsed is None:
                continue
            name, addr, domain = parsed
            local = addr.split("@", 1)[0]
            if domain in system_domains:
                filtered_system += 1
                continue
            if local in _NOREPLY_LOCALPARTS:
                filtered_noreply += 1
                continue
            # First occurrence wins the name (later ones are the same person).
            by_email.setdefault(addr, (name, domain))

        log.info(
            "confirmed job-search emails scanned=%d; senders kept=%d "
            "(filtered: system/board/free=%d, no-reply/automated=%d)",
            seen, len(by_email), filtered_system, filtered_noreply,
        )

        seeded = 0
        for addr, (name, domain) in sorted(by_email.items()):
            contact_id = uuid5(NAMESPACE_URL, f"contact:{tc.tenant_id}:{addr}")
            await g.merge_contact(
                tenant_context=tc, contact_id=contact_id, name=name, email=addr,
                company=_company_from_domain(domain),
                degree=None, strength=None, reachability=None,
                capture_source="email", provenance_origin="system_suggested",
            )
            seeded += 1
        log.info(
            "seeded %d system_suggested contacts from email (D222) — the operator "
            "proofs degree/strength/reachability", seeded,
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
    log.info("seeding contacts from the moat senders (S103u, D222)")
    asyncio.run(_run())
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
