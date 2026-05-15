"""ModelChoiceRule — Phase 1 zero with structured skip-reason (D111 cmt 5).

The model_choice category requires both evaluation-quality evidence
(scoring-sheet runs from ``contexts/evaluation/``, currently absent
in Phase 1) and cost evidence to make a meaningful model
substitution recommendation. Phase 1 ships zero recommendations and
raises ``SubstrateGapError`` carrying a structured
``CategorySkipReason`` the engine captures on the
``OptimizationRun.skipped_categories`` field per D111 commitment 2.

Phase 2 activates when the scoring-sheet runner ships at
``contexts/evaluation/``.
"""

from __future__ import annotations

from typing import Iterable

from contexts.optimization.application.evidence_context import EvidenceContext
from contexts.optimization.domain import (
    CategorySkipReason,
    RecommendationCandidate,
    RecommendationCategory,
    SubstrateGapError,
)


class ModelChoiceRule:
    """Default model-choice rule (D111 cmt 5; Phase 1 zero)."""

    category: RecommendationCategory = RecommendationCategory.MODEL_CHOICE

    async def evaluate(
        self,
        *,
        evidence_context: EvidenceContext,
    ) -> Iterable[RecommendationCandidate]:
        raise SubstrateGapError(
            category=self.category,
            reason=CategorySkipReason(
                reason_code="substrate_gap",
                reason_text=(
                    "model_choice recommendations require evaluation-quality "
                    "evidence from contexts/evaluation/ scoring-sheet runs "
                    "alongside cost evidence; the scoring-sheet runner is "
                    "Phase 2 substrate. No recommendations emitted at Phase 1."
                ),
            ),
        )


__all__ = ["ModelChoiceRule"]
