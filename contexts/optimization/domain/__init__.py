"""Optimization domain layer (D108, D111).

Aggregates and value objects per the D111 commitments:

- ``OptimizationRun`` (D111 cmt 2) at ``optimization_run.py`` — the
  engine-invocation aggregate with status lifecycle plus
  ``skipped_categories`` JSONB. ``CategorySkipReason`` structures
  the skip-reason payload.
- ``Recommendation`` (D111 cmt 3) at ``recommendation.py`` — single
  aggregate with category discriminator; append-only content;
  mutable status.
- ``RecommendationStatusTransition`` (D111 cmt 4) at
  ``recommendation_status_transition.py`` — append-only transition
  row.
- ``RecommendationCategory`` enum (D108) at ``category.py``.
- ``RecommendationStatus`` enum plus ``can_transition`` (D111 cmt 3)
  at ``recommendation_status.py``.
- ``RecommendationCandidate`` (D111 cmt 5) at
  ``recommendation_candidate.py`` — intermediate VO between rules
  and aggregate construction.
- ``RecommendationRule`` Protocol + ``SubstrateGapError`` (D111
  cmt 5) at ``recommendation_rule.py``.
- Evidence citation discriminated union (D111 cmt 7) at
  ``evidence_citation.py`` — concrete shapes per category plus the
  ``CaveatAnnotation`` structured caveat payload.
"""

from contexts.optimization.domain.category import RecommendationCategory
from contexts.optimization.domain.evidence_citation import (
    CAVEAT_INFRASTRUCTURE_SUBSTRATE_CHECK_REQUIRED,
    CaveatAnnotation,
    CostAggregate,
    CostOptimizationEvidenceCitation,
    EvidenceCitation,
    MatcherSuppressionEvidenceCitation,
    RetrievalStrategyEvidenceCitation,
    StrategyComparison,
)
from contexts.optimization.domain.optimization_run import (
    CategorySkipReason,
    OptimizationRun,
    OptimizationRunStatus,
)
from contexts.optimization.domain.recommendation import Recommendation
from contexts.optimization.domain.recommendation_candidate import (
    RecommendationCandidate,
)
from contexts.optimization.domain.recommendation_rule import (
    RecommendationRule,
    SubstrateGapError,
)
from contexts.optimization.domain.recommendation_status import (
    RecommendationStatus,
    can_transition,
)
from contexts.optimization.domain.recommendation_status_transition import (
    RecommendationStatusTransition,
)

__all__ = [
    "CAVEAT_INFRASTRUCTURE_SUBSTRATE_CHECK_REQUIRED",
    "CategorySkipReason",
    "CaveatAnnotation",
    "CostAggregate",
    "CostOptimizationEvidenceCitation",
    "EvidenceCitation",
    "MatcherSuppressionEvidenceCitation",
    "OptimizationRun",
    "OptimizationRunStatus",
    "Recommendation",
    "RecommendationCandidate",
    "RecommendationCategory",
    "RecommendationRule",
    "RecommendationStatus",
    "RecommendationStatusTransition",
    "RetrievalStrategyEvidenceCitation",
    "StrategyComparison",
    "SubstrateGapError",
    "can_transition",
]
