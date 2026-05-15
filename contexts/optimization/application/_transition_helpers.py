"""Internal helpers for the three lifecycle-transition use cases.

acknowledge/apply/reject share the same flow: fetch aggregate, check
``can_transition``, build updated aggregate plus transition row,
persist atomically, emit audit event. The shared helper avoids
duplication while keeping the three public use cases focused on the
target-status they own.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from contexts.audit.domain.ports import AuditPort

from contexts.optimization.application.audit_events import (
    draft_recommendation_transition,
)
from contexts.optimization.domain import (
    Recommendation,
    RecommendationStatus,
    RecommendationStatusTransition,
    can_transition,
)
from contexts.optimization.ports.recommendation_reader import (
    RecommendationReader,
)
from contexts.optimization.ports.recommendation_repository import (
    RecommendationRepository,
)
from shared_kernel.tenant_context import TenantContext


class RecommendationNotFoundError(Exception):
    """Raised when the named recommendation does not exist on this tenant."""


class TransitionNotPermittedError(Exception):
    """Raised when the requested status transition is not allowed.

    Per ``recommendation_status.can_transition``: terminal states
    (applied, rejected) accept no further transitions; acknowledged
    cannot transition back to generated.
    """

    def __init__(
        self,
        *,
        recommendation_id: UUID,
        from_status: RecommendationStatus,
        to_status: RecommendationStatus,
    ) -> None:
        self.recommendation_id = recommendation_id
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"recommendation {recommendation_id} cannot transition from "
            f"{from_status.value} to {to_status.value}"
        )


@dataclass(frozen=True)
class TransitionResult:
    """Result envelope returned by the three lifecycle use cases."""

    recommendation: Recommendation
    transition: RecommendationStatusTransition


async def transition_recommendation(
    *,
    tenant_context: TenantContext,
    recommendation_id: UUID,
    to_status: RecommendationStatus,
    actor_user_id: str,
    reader: RecommendationReader,
    repository: RecommendationRepository,
    audit_port: AuditPort,
    now: datetime | None = None,
) -> TransitionResult:
    if not actor_user_id.strip():
        raise ValueError("actor_user_id must be non-empty")
    timestamp = now or datetime.now(timezone.utc)
    current = await reader.get_recommendation(
        tenant_context=tenant_context,
        recommendation_id=recommendation_id,
    )
    if current is None:
        raise RecommendationNotFoundError(
            f"recommendation {recommendation_id} not found for tenant "
            f"{tenant_context.tenant_id}"
        )
    if not can_transition(
        from_status=current.status,
        to_status=to_status,
    ):
        raise TransitionNotPermittedError(
            recommendation_id=recommendation_id,
            from_status=current.status,
            to_status=to_status,
        )
    updated = Recommendation(
        id=current.id,
        tenant_id=current.tenant_id,
        jurisdiction=current.jurisdiction,
        category=current.category,
        subject=current.subject,
        text=current.text,
        evidence_citations=current.evidence_citations,
        status=to_status,
        generated_at=current.generated_at,
        generated_by_run_id=current.generated_by_run_id,
        last_transition_at=timestamp,
        last_transition_by_user_id=actor_user_id,
    )
    transition = RecommendationStatusTransition(
        id=uuid4(),
        recommendation_id=current.id,
        from_status=current.status,
        to_status=to_status,
        transitioned_by_user_id=actor_user_id,
        transitioned_at=timestamp,
    )
    await repository.persist_status_transition(
        tenant_context=tenant_context,
        updated_recommendation=updated,
        transition=transition,
    )
    await audit_port.emit(
        draft_recommendation_transition(
            tenant_context=tenant_context,
            recommendation=updated,
            actor=actor_user_id,
            from_status=current.status,
        )
    )
    return TransitionResult(recommendation=updated, transition=transition)


__all__ = [
    "RecommendationNotFoundError",
    "TransitionNotPermittedError",
    "TransitionResult",
    "transition_recommendation",
]
