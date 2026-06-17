"""S100 — reindex stored emails so email_chunks carries subject+body vectors.

The D174-email tier-three call needs the clean instrument (subject+body chunk
embeddings), but email_chunks is empty: the live 335 emails arrived via the
scoped sync_email_jobsearch path that never ran index_email (the wired-but-
untriggered miss). This drives the SAME index_email path (chunk → embed →
replace_chunks → graph-merge) over the already-stored emails — the fix at its
natural consumer moment (two-threshold). Idempotent (replace_chunks replaces;
graph merges), so re-runnable.

Counts only to stdout; no content. Run in the api container. Read/write to the
tenant's own stores; not imported by anything.
"""

from __future__ import annotations

import asyncio
import logging
import sys

PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"

log = logging.getLogger("ops.s100_reindex_email")


async def _reindex() -> None:
    from apps.cli._email import build_email_sync_components
    from contexts.email.application.index_email import index_email

    comps = build_email_sync_components(tenant_id=PERSONAL_TENANT_UUID)
    tc = comps["tenant_context"]
    emails = await comps["emails"].list_emails(tenant_context=tc)

    total_chunks = 0
    indexed = 0
    for email in emails:
        n = await index_email(
            tenant_context=tc,
            email=email,
            embedder=comps["embedder"],
            graph_index=comps["graph_index"],
            chunks=comps["chunks"],
        )
        total_chunks += n
        indexed += 1

    print(
        "S100 reindex complete:\n"
        f"  emails reindexed: {indexed}\n"
        f"  chunks embedded:  {total_chunks}"
    )


def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(_reindex())
    return 0


if __name__ == "__main__":
    sys.exit(main())
