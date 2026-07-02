"""Seed system-suggested :Contact nodes from Google Contacts (S103x, D230).

The third contact feeder (D230): the address book, the highest-signal warm ties.
Reads the operator's Google Contacts via the People API through the Nango proxy
(read-only), seeds each **organisation-carrying** contact as a system_suggested
:Contact via merge_contact (``capture_source`` = ``address_book``, company from the
organizations field), for the operator to proof — the same loop the email and
LinkedIn seeds feed. The organisation filter (in the parser) drops company-less
personal contacts that would flood the proof queue.

Dedup: against the email and LinkedIn contacts on the normalized (name, company)
signature (the S103o precedent). On a **match**, the person keeps their existing
``contact_id`` and ``address_book`` is added to their ``capture_source`` set (the
multi-channel confirmation signal) — no duplicate node. New people get a
deterministic uuid5 id, so a re-run is idempotent.

**Operator-gated (consent).** The Google connector holds calendar/gmail/tasks but NOT
a contacts scope, so this runs only after the operator adds
``https://www.googleapis.com/auth/contacts.readonly`` to the Nango Google integration
(dashboard) and re-authorises the connection. Config is read from env:
``NANGO_BASE_URL``, ``NANGO_SECRET_KEY``, ``GOOGLE_CONTACTS_PROVIDER_KEY`` (default
``google-contacts``), ``GOOGLE_CONNECTION_ID`` (the operator's connection ref).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from uuid import NAMESPACE_URL, uuid5

log = logging.getLogger("ops.seed_contacts_from_google")

PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"


def _norm_name(name: str | None) -> str:
    return " ".join((name or "").strip().lower().split())


def _source_from_env():
    from ops.google_contacts_source import NangoProxyGoogleContactsSource

    base = os.environ.get("NANGO_BASE_URL", "")
    secret = os.environ.get("NANGO_SECRET_KEY", "")
    provider = os.environ.get("GOOGLE_CONTACTS_PROVIDER_KEY", "google-contacts")
    connection = os.environ.get("GOOGLE_CONNECTION_ID", "")
    if not (base and secret and connection):
        raise SystemExit(
            "Google Contacts seed is operator-gated: set NANGO_BASE_URL, "
            "NANGO_SECRET_KEY, GOOGLE_CONNECTION_ID (and optionally "
            "GOOGLE_CONTACTS_PROVIDER_KEY). First add the scope "
            "'https://www.googleapis.com/auth/contacts.readonly' to the Nango Google "
            "integration and re-authorise the connection (the connector holds no "
            "contacts scope today)."
        )
    return NangoProxyGoogleContactsSource(
        base_url=base, secret_key=secret, provider_config_key=provider,
        connection_id=connection,
    )


async def _run() -> None:
    from apps.cli._runtime import build_tenant_wiring
    from contexts.daily_driver.domain.contacts import normalize_company
    from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
    from padhanam.config import Neo4jSettings

    source = _source_from_env()
    w = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tc = w.tenant_context
    g = Neo4jGraphRepository.from_settings(Neo4jSettings())
    try:
        parsed = await source.load()
        log.info("Google Contacts: %d org-carrying contacts parsed", len(parsed))

        existing = await g.list_contacts(tenant_context=tc)
        by_sig: dict[str, str] = {}
        by_name: dict[str, str] = {}
        for c in existing:
            n = _norm_name(c.name)
            by_sig[f"{n}|{normalize_company(c.company)}"] = str(c.contact_id)
            by_name.setdefault(n, str(c.contact_id))

        seeded = multichannel = 0
        for sc in parsed:
            n = _norm_name(sc.name)
            if not n:
                continue
            sig = f"{n}|{normalize_company(sc.company)}"
            match_id = by_sig.get(sig) or by_name.get(n)
            if match_id:
                # A person already captured through email/LinkedIn — add the channel.
                await g.add_capture_source(
                    tenant_context=tc, contact_id=match_id, channel="address_book"
                )
                multichannel += 1
                continue
            cid = uuid5(NAMESPACE_URL, f"contact:{tc.tenant_id}:google:{sig}")
            await g.merge_contact(
                tenant_context=tc, contact_id=cid, name=sc.name, email=None,
                company=sc.company, degree=None, strength=None, reachability=None,
                capture_source="address_book", provenance_origin="system_suggested",
            )
            by_sig[sig] = str(cid)
            by_name.setdefault(n, str(cid))
            seeded += 1

        log.info(
            "seeded %d new system_suggested address_book contacts; %d existing "
            "contacts became multi-channel (address_book added) — the operator "
            "proofs (D222/D230)", seeded, multichannel,
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
    log.info("seeding contacts from Google Contacts (S103x, D230)")
    asyncio.run(_run())
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
