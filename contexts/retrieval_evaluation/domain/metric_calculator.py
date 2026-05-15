"""MetricCalculator Protocol + value objects (D111 commitment 6).

The pluggable retrieval-evaluation metric abstraction operationalising
the vendor-flexibility principle at ``charter/principles.md``. Two
methods on the Protocol: per-query metric computation and per-strategy
aggregation. Both are on the Protocol because the runner at
``contexts/retrieval_evaluation/application/run_retrieval_evaluation.py``
consumes both per-query primitives and per-strategy aggregation
primitives; a single-method Protocol would leave aggregation hardcoded
against the default implementation and make "swap the metric
calculator" meaningless at the aggregation surface — which is where
Phase 2 graded-relevance implementations most legitimately differ
(trimmed mean, median, weighted-by-query-difficulty mean).

``BinaryRelevanceMetrics`` at the sibling
``binary_relevance_metrics.py`` ships as the default implementation,
absorbing the recall@k / precision@k / MRR / mean / latency-percentile
primitives previously at ``metrics.py``. Phase 2 implementations (nDCG,
MAP per D105 deferred alternatives) land as siblings without runner
change.

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Protocol, Sequence
from uuid import UUID


@dataclass(frozen=True)
class PerQueryMetrics:
    """Per-query metric output from ``compute_per_query``.

    Mirrors the metric-bearing fields on
    ``EvaluationResult`` per D110 commitment 3: ``recall_at_k`` and
    ``precision_at_k`` keyed by ``SUPPORTED_K_VALUES``; ``mrr``
    quantised to four decimal places per the schema's
    ``numeric(6,4)`` constraint.
    """

    recall_at_k: Mapping[int, float]
    precision_at_k: Mapping[int, float]
    mrr: Decimal


@dataclass(frozen=True)
class AggregatedMetrics:
    """Per-strategy aggregated metric output from ``aggregate_per_strategy``.

    Mirrors the ``EvaluationAggregate`` fields per D110 commitment 4.
    Latency percentiles use the nearest-rank NIST definition for p50
    and p95; mean is integer-rounded via ROUND_HALF_EVEN.
    """

    recall_at_k_mean: Mapping[int, float]
    precision_at_k_mean: Mapping[int, float]
    mrr_mean: Decimal
    latency_ms_p50: int
    latency_ms_p95: int
    latency_ms_mean: int


class MetricCalculator(Protocol):
    """Pluggable retrieval-evaluation metric abstraction (D111 cmt 6)."""

    def compute_per_query(
        self,
        *,
        returned: Sequence[UUID],
        expected: Sequence[UUID],
    ) -> PerQueryMetrics:
        """Compute per-query metrics from returned and expected chunk IDs."""
        ...

    def aggregate_per_strategy(
        self,
        *,
        per_query_results: Sequence[PerQueryMetrics],
        latencies_ms: Sequence[int],
    ) -> AggregatedMetrics:
        """Aggregate per-query results plus latencies across a strategy."""
        ...


__all__ = [
    "AggregatedMetrics",
    "MetricCalculator",
    "PerQueryMetrics",
]
