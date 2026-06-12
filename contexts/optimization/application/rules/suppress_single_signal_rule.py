"""SuppressSingleSignalRule — the first matcher rule (D185/S91).

Reads the matcher-quality producer's latest run (S90) off the EvidenceContext and,
when single-signal keyword-on-name candidate edges are present, emits one
``RecommendationCandidate`` to suppress them: the weak ``goal-name`` tier is the
cross-goal keyword-collision noise band (single_signal_count == candidate_count by
construction), so removing it drops the single-signal share to ~0 without touching
a confirmed edge.

The candidate carries a ``MatcherSuppressionEvidenceCitation``: the matcher-quality
run id, the current count + share, the projected share (the impact), and the rule's
confidence. (The inference-shaped ``RecommendationCandidate`` has no first-class
impact/confidence field, so the structured evidence is the citation's job — D111
cmt 7. The recommendation is still **advisory** in S91a; the apply path is S91b,
gated on the ground-truth review of the surfaced edges.)

Substrate gap (the matcher producer's reader is absent, or no run exists yet)
raises ``SubstrateGapError`` the engine records on ``skipped_categories`` —
mirroring the Phase-2 inference rules.
"""

from __future__ import annotations

from typing import Iterable

from contexts.optimization.application.evidence_context import EvidenceContext
from contexts.optimization.domain import (
    CategorySkipReason,
    MatcherSuppressionEvidenceCitation,
    RecommendationCandidate,
    RecommendationCategory,
    SubstrateGapError,
)

# The rule's confidence that the single-signal tier is suppressible noise. High,
# but not 1.0: the structural cut is precise (the weakest, candidate-only tier),
# yet the ground-truth gate is what confirms each is a collision, not a real
# match the matcher missed (S91a). The confidence is honest about that order.
_SUPPRESSION_CONFIDENCE: float = 0.9
# Suppressing the single-signal tier projects its share to zero by construction.
_PROJECTED_SINGLE_SIGNAL_SHARE: float = 0.0


class SuppressSingleSignalRule:
    """Default matcher single-signal suppression rule (D185/S91)."""

    category: RecommendationCategory = RecommendationCategory.MATCHER_SUPPRESSION

    async def evaluate(
        self,
        *,
        evidence_context: EvidenceContext,
    ) -> Iterable[RecommendationCandidate]:
        reader = evidence_context.matcher_quality_run_reader
        if reader is None:
            raise SubstrateGapError(
                category=self.category,
                reason=CategorySkipReason(
                    reason_code="substrate_gap",
                    reason_text=(
                        "matcher_suppression requires the matcher-quality "
                        "producer's reader (D185); it is not wired in this "
                        "EvidenceContext. No recommendations emitted."
                    ),
                ),
            )
        run = await reader.get_latest_run(
            tenant_context=evidence_context.tenant_context
        )
        if run is None:
            raise SubstrateGapError(
                category=self.category,
                reason=CategorySkipReason(
                    reason_code="no_matcher_quality_run",
                    reason_text=(
                        "matcher_suppression requires at least one recorded "
                        "matcher-quality run (S90); none exists for this "
                        "tenant. No recommendations emitted."
                    ),
                ),
            )
        m = run.metrics
        if m.single_signal_count == 0:
            # Substrate present, no actionable signal — return empty (the
            # retrieval-rule contract for "nothing to recommend").
            return ()
        citation = MatcherSuppressionEvidenceCitation(
            matcher_quality_run_id=run.id,
            edge_count=m.edge_count,
            single_signal_count=m.single_signal_count,
            current_single_signal_share=m.single_signal_share,
            projected_single_signal_share=_PROJECTED_SINGLE_SIGNAL_SHARE,
            confidence=_SUPPRESSION_CONFIDENCE,
        )
        candidate = RecommendationCandidate(
            category=self.category,
            subject="Suppress single-signal keyword-on-name candidate matches",
            text=(
                f"{m.single_signal_count} SERVES edges "
                f"({m.single_signal_share:.4f} of {m.edge_count}) rest on the "
                "single weak goal-name keyword-on-name basis — the candidate "
                "tier, cross-goal keyword collisions. Suppressing them projects "
                "the single-signal share to ~0 and touches no confirmed edge. "
                "Apply is gated on ground-truth confirmation that each is noise."
            ),
            evidence_citations=(citation,),
        )
        return (candidate,)


__all__ = ["SuppressSingleSignalRule"]
