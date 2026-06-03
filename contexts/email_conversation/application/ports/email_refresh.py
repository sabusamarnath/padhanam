"""EmailRefreshPort — refresh-before-answer seam (D150, D152, P15, S56b).

The email-conversation cell refreshes the mailbox at turn-open before
querying the email store (D152 Option A: full-pull-in-turn within a tier
budget, fall back to the cached store on miss). The cell depends on this
port **only** — it never reaches through to ``sync_email``; the apps
composition root wires the port to an adapter driving the D151 ``sync_email``
full pull (commit 3). This is the boundary that keeps the deferred
background-sync optimization a wiring swap (the port implementation
changes) rather than a cell rewrite.

``refresh`` returns None on success; raises ``EmailRefreshError`` on a
refresh that could not complete (Nango/Gmail unreachable, a pipeline
error), which the cell catches (with ``asyncio.TimeoutError`` on budget
overrun) and answers from the cached store with a staleness note.
"""

from __future__ import annotations

from typing import Protocol

from shared_kernel.tenant_context import TenantContext


class EmailRefreshError(Exception):
    """An email refresh could not complete; serve the cached store."""


class EmailRefreshPort(Protocol):
    async def refresh(self, *, tenant_context: TenantContext) -> None:
        """Refresh the tenant's mailbox (D151 full pull). Raises EmailRefreshError on failure."""
        ...


__all__ = ["EmailRefreshError", "EmailRefreshPort"]
