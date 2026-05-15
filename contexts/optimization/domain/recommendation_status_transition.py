"""RecommendationStatusTransition value object (D111 commitment 4).

One row per status change. Append-only; provides the full status-
history audit trail without mutating the parent Recommendation
aggregate's lifecycle fields. The parent's
``last_transition_at`` and ``last_transition_by_user_id`` mirror
the most recent row's values for read-time convenience; the
transitions are canonical for any audit drill-down.

Domain code is framework-free per D16 — stdlib dataclasses only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from contexts.optimization.domain.recommendation_status import (
    RecommendationStatus,
)


@dataclass(frozen=True)
class RecommendationStatusTransition:
    """Append-only status transition row (D111 commitment 4)."""

    id: UUID
    recommendation_id: UUID
    from_status: RecommendationStatus
    to_status: RecommendationStatus
    transitioned_by_user_id: str
    transitioned_at: datetime

    def __post_init__(self) -> None:
        if not self.transitioned_by_user_id.strip():
            raise ValueError("transitioned_by_user_id must be non-empty")
        if self.from_status == self.to_status:
            raise ValueError(
                "from_status and to_status must differ "
                f"(both {self.from_status.value})"
            )


__all__ = ["RecommendationStatusTransition"]
