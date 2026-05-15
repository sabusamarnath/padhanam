"""Recommendation aggregate root (D111 commitment 3).

Single-aggregate-with-category-discriminator shape per D111
alternative (a) rejection of four sibling aggregates: the lifecycle
is uniform across categories per D108's five-field commitment, the
read surface stays cleaner with one table and one reader, and the
polymorphic evidence_citations field handles per-category citation
differences cleanly via the discriminated union at
``evidence_citation.py``.

The aggregate is mutable for status transitions (per D111 commitment
3) and append-only for content (``text`` and ``evidence_citations``
do not mutate after generation per D111 alternative (g) — corrections
happen as new recommendations in a new optimization run).
``last_transition_at`` and ``last_transition_by_user_id`` mirror the
most recent ``RecommendationStatusTransition`` row for read-time
convenience without forcing a join on every read; the transitions
table is canonical for any audit drill-down.

``generated_by_run_id`` is NOT NULL with FK to ``optimization_runs.id``
— Phase 1 has no user-initiated recommendations, so every
recommendation traces to an engine invocation.

Domain code is framework-free per D16 — stdlib dataclasses only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from contexts.optimization.domain.category import RecommendationCategory
from contexts.optimization.domain.evidence_citation import EvidenceCitation
from contexts.optimization.domain.recommendation_status import (
    RecommendationStatus,
)


@dataclass(frozen=True)
class Recommendation:
    """Recommendation aggregate root (D111 commitment 3)."""

    id: UUID
    tenant_id: UUID
    jurisdiction: str
    category: RecommendationCategory
    subject: str
    text: str
    evidence_citations: tuple[EvidenceCitation, ...]
    status: RecommendationStatus
    generated_at: datetime
    generated_by_run_id: UUID
    last_transition_at: datetime
    last_transition_by_user_id: str | None

    def __post_init__(self) -> None:
        if not self.jurisdiction.strip():
            raise ValueError("jurisdiction must be non-empty")
        if not self.subject.strip():
            raise ValueError("subject must be non-empty")
        if not self.text.strip():
            raise ValueError("text must be non-empty")
        if not self.evidence_citations:
            raise ValueError("evidence_citations must not be empty")
        # Citation/category coherence: at least one citation must
        # match the recommendation's category. Phase 2 categories
        # will extend the union with their own citation shapes; the
        # coherence rule generalises.
        if not any(
            citation.category == self.category
            for citation in self.evidence_citations
        ):
            raise ValueError(
                "evidence_citations must include at least one citation "
                f"of matching category {self.category.value}"
            )
        if self.status is RecommendationStatus.GENERATED:
            if self.last_transition_by_user_id is not None:
                raise ValueError(
                    "last_transition_by_user_id must be None on generated status"
                )
        else:
            if not (
                self.last_transition_by_user_id
                and self.last_transition_by_user_id.strip()
            ):
                raise ValueError(
                    f"last_transition_by_user_id must be set on status "
                    f"{self.status.value}"
                )

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            RecommendationStatus.APPLIED,
            RecommendationStatus.REJECTED,
        }


__all__ = ["Recommendation"]
