"""Classify the stored job-search emails for the personal dogfood tenant (S89, D183).

Runs the rules-only classifier over the live emails and persists each verdict on
the email row (``job_search_kind``). Idempotent. Prints **counts only** to
stdout; writes a **local, gitignored** review artefact (/tmp/s89_review/, sender
domain + subject + kind) so the operator can eyeball the flagged set for residual
alert leakage — that artefact stays local, never committed. Run inside
``padhanam-api`` via ``make classify-job-search``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections import Counter

log = logging.getLogger("ops.classify_job_search")

PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"
_REVIEW_DIR = "/tmp/s89_review"


async def _run() -> None:
    import re

    from apps.cli._runtime import build_tenant_wiring
    from contexts.email.adapters.outbound.postgres.email_store import (
        PostgresEmailStore,
    )
    from contexts.email.application.classify_job_search import (
        classify_job_search_emails,
    )
    from contexts.email.domain.job_search_classifier import classify
    from shared_kernel import TenantId

    wiring = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tc = wiring.tenant_context
    sf = wiring.session_factory

    async def _resolver(_tid: TenantId):
        return sf

    store = PostgresEmailStore(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=TenantId(str(tc.tenant_id)),
    )

    # Local review artefact (sender domain + subject + kind) before the verdict
    # write — for the operator's residual-leak eyeball. Local only, gitignored.
    rows = await store.list_emails(tenant_context=tc)
    os.makedirs(_REVIEW_DIR, exist_ok=True)
    with open(f"{_REVIEW_DIR}/classified.tsv", "w") as f:
        f.write("from_domain\tsubject\tis_job_search\tkind\n")
        for e in rows:
            is_js, kind = classify(e.from_address, e.subject)
            m = re.search(r"@([\w.-]+)", e.from_address or "")
            f.write(
                f"{(m.group(1).lower() if m else '')}\t{e.subject or ''}\t"
                f"{'yes' if is_js else 'no'}\t{kind or ''}\n"
            )

    result = await classify_job_search_emails(tenant_context=tc, emails=store)
    confirmed = {k: v for k, v in result.by_kind.items() if k != "none"}
    log.info(
        "classified %d emails: %d job-search (%s), %d not; rows updated=%d",
        result.total,
        result.confirmed,
        ", ".join(f"{k} {v}" for k, v in sorted(confirmed.items())),
        result.by_kind.get("none", 0),
        result.updated,
    )
    log.info("review artefact (local, uncommitted): %s/classified.tsv", _REVIEW_DIR)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.setLevel(logging.INFO)
    log.info("classifying job-search emails for the personal dogfood tenant (S89, D183)")
    asyncio.run(_run())
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
