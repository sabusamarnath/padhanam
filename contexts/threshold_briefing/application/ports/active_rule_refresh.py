"""ActiveRuleRefreshPort — refresh-then-evaluate seam (D146, D153, S57).

Before evaluating, the ThresholdEvaluator syncs the active-rule
substrates so the state it reads is fresh — the proactivity property: a
scheduled scan cannot lean on the conversation cell's in-turn refresh
(D150), which only runs when the user engages. At Phase 2-A the only
active-rule substrate is calendar, so the wiring adapter drives the D149
``sync_calendar`` scoped full pull. The evaluator holds no vendor or
pipeline detail — it knows only "refresh the active substrates, or tell
me you could not"; the threshold context never imports ``sync_calendar``
(D146 consumer-port discipline), so the eventual swap to a background
sync is a wiring change, not an evaluator change.

``refresh`` returns None on success. A refresh that cannot complete
raises ``ActiveRuleRefreshError``; the evaluator logs and proceeds to
evaluate over the last-synced state rather than skipping the scan (a
stale-but-present evaluation beats no evaluation for a proactive surface).
"""

from __future__ import annotations

from typing import Protocol

from shared_kernel.tenant_context import TenantContext


class ActiveRuleRefreshError(Exception):
    """An active-rule substrate refresh could not complete; evaluate stale."""


class ActiveRuleRefreshPort(Protocol):
    async def refresh(self, *, tenant_context: TenantContext) -> None:
        """Refresh the active-rule substrates (calendar at Phase 2-A).

        Returns on a completed refresh. Raises ``ActiveRuleRefreshError``
        on a refresh that could not complete.
        """
        ...


__all__ = ["ActiveRuleRefreshError", "ActiveRuleRefreshPort"]
