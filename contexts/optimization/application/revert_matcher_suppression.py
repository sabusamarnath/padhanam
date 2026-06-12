"""revert_matcher_suppression use case — the flag-level revert (D186/S91b).

The clean whole-rule revert: write the active policy back to
``suppress_single_signal=False`` so the matcher stops suppressing on its next run.
Makes the loop **reversible** — the apply is not a one-way door. Idempotent.

Flag-level only: this turns the *whole* rule off. Keeping some suppressed edges
while dropping the rest (a per-edge override) is the deferred override layer, not
this. The recommendation's APPLIED status is the audit record and is left intact;
re-applying re-arms the flag.

Optimization writes the policy through ``matcher_policy.ports``; it never imports
the matcher or ``daily_driver`` (the seam, D186).
"""

from __future__ import annotations

from contexts.matcher_policy.domain import MatcherPolicy
from contexts.matcher_policy.ports import MatcherPolicyRepository
from shared_kernel.tenant_context import TenantContext


async def revert_matcher_suppression(
    *,
    tenant_context: TenantContext,
    policy_repository: MatcherPolicyRepository,
) -> None:
    """Disable single-signal suppression (write the flag back to false)."""
    await policy_repository.set_policy(
        tenant_context=tenant_context,
        policy=MatcherPolicy(suppress_single_signal=False),
    )


__all__ = ["revert_matcher_suppression"]
