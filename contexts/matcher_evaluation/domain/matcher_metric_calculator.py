"""MatcherMetricCalculator — the pluggable matcher metric abstraction (D185).

Mirrors ``retrieval_evaluation``'s ``MetricCalculator`` Protocol +
``BinaryRelevanceMetrics`` default (D111 commitment 6), operationalising the
vendor-flexibility principle: the metric definition is swappable behind a
Protocol. ``StructuralMatcherMetrics`` is the S90 default — it aggregates the
classified ``MatcherQualitySample`` into the three structural rates.

The calculator is **generic**: it counts the booleans the sample already carries
and never knows the matcher's basis vocabulary (``goal-name``) or confidence
tiers — that classification happens at the composition root where the matcher's
edges are projected, keeping this context independent of ``daily_driver`` (D17).

Pure domain (D16): stdlib only, no I/O.
"""

from __future__ import annotations

from typing import Protocol

from contexts.matcher_evaluation.domain.matcher_quality_metrics import (
    MatcherQualityMetrics,
)
from contexts.matcher_evaluation.domain.matcher_quality_sample import (
    MatcherQualitySample,
)


class MatcherMetricCalculator(Protocol):
    """Computes structural quality metrics from a classified matcher sample."""

    def compute(self, sample: MatcherQualitySample) -> MatcherQualityMetrics:
        """Return the run's metrics. Pure — no I/O, no side effects."""
        ...


class StructuralMatcherMetrics:
    """Default MatcherMetricCalculator (D185, S90).

    Single-signal share, candidate-to-confirmed ratio, and orphan rate over the
    classified sample. Orphans are units with no edge: every unit id in the
    sample that no edge references.
    """

    def compute(self, sample: MatcherQualitySample) -> MatcherQualityMetrics:
        linked_unit_ids = {edge.unit_id for edge in sample.edges}
        orphan_count = sum(
            1 for uid in sample.unit_ids if uid not in linked_unit_ids
        )
        return MatcherQualityMetrics(
            edge_count=len(sample.edges),
            unit_count=len(sample.unit_ids),
            orphan_count=orphan_count,
            single_signal_count=sum(
                1 for e in sample.edges if e.is_single_signal
            ),
            candidate_count=sum(1 for e in sample.edges if e.is_candidate),
            confirmed_count=sum(1 for e in sample.edges if e.is_confirmed),
        )


__all__ = ["MatcherMetricCalculator", "StructuralMatcherMetrics"]
