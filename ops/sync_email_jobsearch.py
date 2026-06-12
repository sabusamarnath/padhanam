"""Pull the job-search email slice for the personal dogfood tenant (S88, D183).

The operator-gated live trigger for email job-search capture: ensures the
personal tenant's ``email_connections`` row points at the operator-provisioned
Nango ``google-mail`` connection (gmail.readonly, proven in the S87 spike), then
runs ``sync_email`` with the **job-search-scoped query** — applicant-tracking and
recruiter senders + application / interview / offer subjects, lifted from the
spike. Idempotent (``upsert_email`` on message_id). Read-only.

This is the *scoped* pull (D183): the optional ``query`` lists only the
job-search slice, so the set-diff-tombstone is skipped (a scoped pull is not
authoritative over the window). It runs **without the embedder/graph index**
(``embedder=None``) — the rules-only classifier (S89) keys on sender/subject
metadata, not the body embeddings the store computes for the general signal
layer. The general whole-window pull (no ``query``) stays D151's full intake.

Email content persists only in the encrypted store (D21, unreadable at rest);
this script prints **counts only** — no senders, subjects, or bodies. Must run
where the personal-tenant Postgres host resolves and Nango is reachable (inside
``padhanam-api``, via ``make sync-email-jobsearch``).

Operator pre-flight: provision a Nango ``google-mail`` integration with the
``gmail.readonly`` scope on the connected Google account, obtain the connection
reference, and set ``EMAIL_CONNECTION_REF`` (plus ``NANGO_SECRET_KEY``) in the
gitignored ``.env``.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from uuid import UUID

log = logging.getLogger("ops.sync_email_jobsearch")

# Personal dogfood tenant (ops/dogfood_provision.py).
PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"

# Deterministic id for the personal tenant's single google-mail connection.
EMAIL_CONNECTION_ID = UUID("00000000-0000-4000-8000-0000008800a1")

# The 90-day window the S87 spike measured.
WINDOW_DAYS = 90

# The job-search scope, lifted verbatim from the S87 spike (/tmp/s87_spike/
# spike.py): applicant-tracking / recruiter senders + application-shaped
# subjects. ANDed into the window bound by the adapter (D183). Vendor (Gmail q)
# syntax lives here in the ops/run layer, never in the email domain.
_SENDERS = [
    "greenhouse.io", "hire.lever.co", "lever.co", "myworkday.com", "workday.com",
    "ashbyhq.com", "smartrecruiters.com", "linkedin.com", "indeed.com",
    "ziprecruiter.com", "jobvite.com", "icims.com", "taleo.net", "breezy.hr",
    "workable.com", "teamtailor.com", "recruitee.com", "wellfound.com",
    "otta.com", "hired.com",
]
_SUBJECTS = [
    "application", "applied", "interview", "offer", "recruiter", "assessment",
    "screening", "next steps", "your candidacy", "position", "role at",
]
JOB_SEARCH_QUERY = " OR ".join(
    [f"from:{d}" for d in _SENDERS]
    + [f"subject:{w.replace(' ', '-')}" for w in _SUBJECTS]
)


async def _run() -> None:
    from apps.cli._runtime import build_tenant_wiring
    from contexts.email.adapters.outbound.nango.nango_proxy_email_adapter import (
        NangoProxyEmailAdapter,
    )
    from contexts.email.adapters.outbound.postgres.connection_repository import (
        PostgresConnectionRepository,
    )
    from contexts.email.adapters.outbound.postgres.email_store import (
        PostgresEmailStore,
    )
    from contexts.email.application.sync_email import sync_email
    from contexts.email.domain.connection import Connection
    from contexts.email.domain.sync_trigger import EmailSyncTrigger
    from padhanam.config.email import EmailSettings
    from shared_kernel import TenantId

    settings = EmailSettings()
    if not settings.email_connection_ref:
        raise SystemExit(
            "EMAIL_CONNECTION_REF is empty — provision the Nango google-mail "
            "connection (gmail.readonly) and set it in .env before syncing."
        )

    wiring = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tenant_context = wiring.tenant_context
    session_factory = wiring.session_factory

    async def _resolver(_tid: TenantId):
        return session_factory

    bound = TenantId(str(tenant_context.tenant_id))
    connections = PostgresConnectionRepository(
        per_tenant_sessionmaker_resolver=_resolver, bound_tenant_id=bound
    )
    store = PostgresEmailStore(
        per_tenant_sessionmaker_resolver=_resolver, bound_tenant_id=bound
    )

    now = datetime.now(timezone.utc)
    await connections.save_connection(
        tenant_context=tenant_context,
        connection=Connection(
            id=EMAIL_CONNECTION_ID,
            tenant_id=UUID(str(tenant_context.tenant_id)),
            jurisdiction=tenant_context.jurisdiction,
            provider="google_mail",
            provider_config_key=settings.email_provider_config_key,
            provider_connection_ref=settings.email_connection_ref,
            created_at=now,
            updated_at=now,
        ),
    )
    log.info("ensured google-mail connection %s", EMAIL_CONNECTION_ID)

    source = NangoProxyEmailAdapter(
        base_url=settings.nango_base_url, secret_key=settings.nango_secret_key
    )
    result = await sync_email(
        tenant_context=tenant_context,
        connection_id=EMAIL_CONNECTION_ID,
        trigger=EmailSyncTrigger.POLL,
        message_source=source,
        connections=connections,
        emails=store,
        email_reader=store,
        embedder=None,          # rules-only on metadata (S89); skip chunk/embed
        graph_index=None,
        chunks=None,
        window_days=WINDOW_DAYS,
        query=JOB_SEARCH_QUERY,  # the scoped job-search slice (D183)
        now=now,
    )
    log.info(
        "job-search email sync complete: fetched=%d upserted=%d tombstoned=%d changed=%d",
        result.fetched,
        result.upserted,
        result.tombstoned,
        len(result.changed_message_ids),
    )


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.setLevel(logging.INFO)
    log.info("syncing the job-search email slice for the personal dogfood tenant (S88, D183)")
    asyncio.run(_run())
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
