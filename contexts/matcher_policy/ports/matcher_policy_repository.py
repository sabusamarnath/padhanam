"""Write-side port for the matcher-policy seam (D186/S91b).

Optimization writes the active policy here on apply (the write half of the seam).
Upsert semantics — one policy row per tenant; setting it again is idempotent.
Ports layer is pure per D16 — no SQLAlchemy, no asyncpg.
"""

from __future__ import annotations

from typing import Protocol

from shared_kernel.tenant_context import TenantContext

from contexts.matcher_policy.domain import MatcherPolicy


class MatcherPolicyRepository(Protocol):
    """Persists the active matcher policy for a tenant (upsert)."""

    async def set_policy(
        self, *, tenant_context: TenantContext, policy: MatcherPolicy
    ) -> None:
        """Upsert the tenant's active policy. Idempotent."""
        ...


__all__ = ["MatcherPolicyRepository"]
