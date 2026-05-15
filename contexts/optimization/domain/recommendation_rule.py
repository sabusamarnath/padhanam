"""RecommendationRule Protocol (D111 commitment 5).

The pluggable rule abstraction. Each rule implements
``evaluate(evidence_context)`` returning ``Iterable[
RecommendationCandidate]``. The optimization engine iterates
registered rules at invocation time; rules consume the
``EvidenceContext`` (which wraps the four consumer-defined reader
ports per D111 commitment 5) and produce candidate sets.

A rule that finds no actionable signal returns an empty iterable;
a rule that cannot run due to substrate gaps raises
``SubstrateGapError`` carrying a structured ``CategorySkipReason``
the engine captures on the parent ``OptimizationRun`` aggregate's
``skipped_categories`` field.

Phase 1 ships four default implementations covering the four D108
categories. Two produce substantive candidates (retrieval_strategy,
cost_optimization); two raise SubstrateGapError because their input
substrate is Phase 2 territory (model_choice, prompt_revision both
require scoring-sheet evaluation runs from contexts/evaluation/).

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from typing import Iterable, Protocol

from contexts.optimization.domain.category import RecommendationCategory
from contexts.optimization.domain.optimization_run import CategorySkipReason
from contexts.optimization.domain.recommendation_candidate import (
    RecommendationCandidate,
)


# ``evidence_context`` argument type is the application-layer
# ``EvidenceContext`` dataclass at
# ``contexts/optimization/application/evidence_context.py``. The
# Protocol intentionally does not import that class because domain
# code must not depend on application code per the hexagonal layer
# contract (D16); the annotation below is a string literal under
# PEP 563 lazy evaluation. The class lives at application not domain
# because it wraps producer-context reader ports — concrete cross-
# context types — that domain cannot reference.


class SubstrateGapError(Exception):
    """Raised by rules when their input substrate is unavailable.

    The engine catches this, records the structured skip reason on
    the parent OptimizationRun aggregate's ``skipped_categories``
    field, and continues iteration with the next rule. The category
    field on the exception names which D108 category the rule
    serves so the engine can key the skip-reason map correctly.
    """

    def __init__(
        self,
        *,
        category: RecommendationCategory,
        reason: CategorySkipReason,
    ) -> None:
        self.category = category
        self.reason = reason
        super().__init__(f"{category.value}: {reason.reason_text}")


class RecommendationRule(Protocol):
    """Pluggable rule that produces RecommendationCandidates."""

    @property
    def category(self) -> RecommendationCategory:
        """The D108 category this rule serves."""
        ...

    async def evaluate(
        self,
        *,
        evidence_context: "object",
    ) -> Iterable[RecommendationCandidate]:
        """Evaluate the rule against producer-context evidence.

        Raises ``SubstrateGapError`` if the rule's required input
        substrate is unavailable. Returns an empty iterable if the
        substrate is available but no actionable signal surfaces.
        """
        ...


__all__ = [
    "RecommendationRule",
    "SubstrateGapError",
]
