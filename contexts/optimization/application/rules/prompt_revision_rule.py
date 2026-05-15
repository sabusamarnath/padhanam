"""PromptRevisionRule — Phase 1 zero with structured skip-reason (D111 cmt 5).

The prompt_revision category requires scoring-sheet evaluation runs
showing consistent failure patterns to suggest prompt adjustments;
the substrate (``contexts/evaluation/`` scoring-sheet runner) is
Phase 2 territory. Phase 1 ships zero recommendations and raises
``SubstrateGapError`` carrying a structured ``CategorySkipReason``
the engine captures on the ``OptimizationRun.skipped_categories``
field per D111 commitment 2.

Phase 2 activates when the scoring-sheet runner ships and produces
criterion-failure signal at ``contexts/evaluation/``.
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


class PromptRevisionRule:
    """Default prompt-revision rule (D111 cmt 5; Phase 1 zero)."""

    category: RecommendationCategory = RecommendationCategory.PROMPT_REVISION

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
                    "prompt_revision recommendations require scoring-sheet "
                    "evaluation runs from contexts/evaluation/ showing "
                    "consistent criterion-failure patterns; the scoring-sheet "
                    "runner is Phase 2 substrate. No recommendations emitted "
                    "at Phase 1."
                ),
            ),
        )


__all__ = ["PromptRevisionRule"]
