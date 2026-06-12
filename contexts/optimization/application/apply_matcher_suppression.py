"""apply_matcher_suppression use case — the first automated apply (D186/S91b).

The category-aware apply for a ``matcher_suppression`` recommendation: applying it
**writes active policy** to the neutral ``MatcherPolicy`` surface (the write half
of the seam) and transitions the recommendation to ``APPLIED``. The matcher reads
that policy on its next run and suppresses single-signal candidates — the loop
closes.

Optimization writes the policy through ``matcher_policy.ports`` (the cross-context
seam); it never imports the matcher or ``daily_driver``. Idempotent: the policy
write is an upsert, and re-applying an already-applied recommendation re-asserts
the policy without erroring (the status is already terminal).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from contexts.audit.domain.ports import AuditPort

from contexts.matcher_policy.domain import MatcherPolicy
from contexts.matcher_policy.ports import MatcherPolicyRepository
from contexts.optimization.application._transition_helpers import (
    RecommendationNotFoundError,
)
from contexts.optimization.application.apply_recommendation import (
    apply_recommendation,
)
from contexts.optimization.domain import (
    Recommendation,
    RecommendationCategory,
    RecommendationStatus,
)
from contexts.optimization.ports.recommendation_reader import (
    RecommendationReader,
)
from contexts.optimization.ports.recommendation_repository import (
    RecommendationRepository,
)
from shared_kernel.tenant_context import TenantContext


async def apply_matcher_suppression(
    *,
    tenant_context: TenantContext,
    recommendation_id: UUID,
    actor_user_id: str,
    reader: RecommendationReader,
    repository: RecommendationRepository,
    audit_port: AuditPort,
    policy_repository: MatcherPolicyRepository,
    now: datetime | None = None,
) -> Recommendation:
    """Apply a matcher_suppression recommendation: write policy + mark APPLIED.

    Returns the applied recommendation. Idempotent.
    """
    current = await reader.get_recommendation(
        tenant_context=tenant_context,
        recommendation_id=recommendation_id,
    )
    if current is None:
        raise RecommendationNotFoundError(
            f"recommendation {recommendation_id} not found on this tenant"
        )
    if current.category is not RecommendationCategory.MATCHER_SUPPRESSION:
        raise ValueError(
            "apply_matcher_suppression only applies matcher_suppression "
            f"recommendations; got {current.category.value}"
        )
    # The apply's effect: write the active policy (idempotent upsert). This is
    # the first automated apply in the platform — an approved recommendation
    # changing behaviour by itself, through the neutral seam.
    await policy_repository.set_policy(
        tenant_context=tenant_context,
        policy=MatcherPolicy(suppress_single_signal=True),
    )
    if current.status is RecommendationStatus.APPLIED:
        # Idempotent re-apply: the policy is re-asserted; the status is already
        # terminal, so there is no transition to make.
        return current
    result = await apply_recommendation(
        tenant_context=tenant_context,
        recommendation_id=recommendation_id,
        actor_user_id=actor_user_id,
        reader=reader,
        repository=repository,
        audit_port=audit_port,
        now=now,
    )
    return result.recommendation


__all__ = ["apply_matcher_suppression"]
