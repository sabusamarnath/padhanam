"""acknowledge_recommendation use case (D111 commitments 3, 8)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from contexts.audit.domain.ports import AuditPort

from contexts.optimization.application._transition_helpers import (
    TransitionResult,
    transition_recommendation,
)
from contexts.optimization.domain import RecommendationStatus
from contexts.optimization.ports.recommendation_reader import (
    RecommendationReader,
)
from contexts.optimization.ports.recommendation_repository import (
    RecommendationRepository,
)
from shared_kernel.tenant_context import TenantContext


async def acknowledge_recommendation(
    *,
    tenant_context: TenantContext,
    recommendation_id: UUID,
    actor_user_id: str,
    reader: RecommendationReader,
    repository: RecommendationRepository,
    audit_port: AuditPort,
    now: datetime | None = None,
) -> TransitionResult:
    """Transition a recommendation to ``acknowledged`` status."""
    return await transition_recommendation(
        tenant_context=tenant_context,
        recommendation_id=recommendation_id,
        to_status=RecommendationStatus.ACKNOWLEDGED,
        actor_user_id=actor_user_id,
        reader=reader,
        repository=repository,
        audit_port=audit_port,
        now=now,
    )


__all__ = ["acknowledge_recommendation"]
