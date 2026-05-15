"""RecommendationCandidate intermediate value object (D111 commitment 5).

Rules return ``RecommendationCandidate`` instances; the optimization
engine wraps each candidate into a full ``Recommendation`` aggregate
at persistence time, assigning the generated UUID, generated_at
timestamp, generated_by_run_id FK, initial generated status, and the
mirroring last_transition_at field. The intermediate value object
decouples rule-produced content (category, subject, text,
evidence_citations) from aggregate identity and lifecycle metadata.

Domain code is framework-free per D16 — stdlib dataclasses only.
"""

from __future__ import annotations

from dataclasses import dataclass

from contexts.optimization.domain.category import RecommendationCategory
from contexts.optimization.domain.evidence_citation import EvidenceCitation


@dataclass(frozen=True)
class RecommendationCandidate:
    """Rule-produced candidate awaiting aggregate construction."""

    category: RecommendationCategory
    subject: str
    text: str
    evidence_citations: tuple[EvidenceCitation, ...]

    def __post_init__(self) -> None:
        if not self.subject.strip():
            raise ValueError("subject must be non-empty")
        if not self.text.strip():
            raise ValueError("text must be non-empty")
        if not self.evidence_citations:
            raise ValueError("evidence_citations must not be empty")
        if not any(
            citation.category == self.category
            for citation in self.evidence_citations
        ):
            raise ValueError(
                "evidence_citations must include at least one citation "
                f"of matching category {self.category.value}"
            )


__all__ = ["RecommendationCandidate"]
