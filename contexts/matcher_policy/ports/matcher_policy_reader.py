"""Read-side port for the matcher-policy seam (D186/S91b).

The matcher reads the active policy here on every run (the read half of the
seam), through a daily_driver policy port the apps bridge implements over this
reader. Returns ``MatcherPolicy.inactive()`` when the tenant has no policy row —
flag off, the S90 baseline behaviour.

Ports layer is pure per D16.
"""

from __future__ import annotations

from typing import Protocol

from shared_kernel.tenant_context import TenantContext

from contexts.matcher_policy.domain import MatcherPolicy


class MatcherPolicyReader(Protocol):
    """Reads the active matcher policy for a tenant."""

    async def get_policy(
        self, *, tenant_context: TenantContext
    ) -> MatcherPolicy:
        """The tenant's active policy, or ``MatcherPolicy.inactive()``."""
        ...


__all__ = ["MatcherPolicyReader"]
