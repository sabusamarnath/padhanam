"""BinaryRelevanceMetrics — default MetricCalculator (D111 cmt 6).

The default implementation of the ``MetricCalculator`` Protocol per
D111 commitment 6. Absorbs the per-D110 metric primitive set
(previously at ``metrics.py``): recall@k, precision@k, and MRR for
per-query computation; mean-across-queries, mean-MRR, and latency
percentiles for per-strategy aggregation.

The math is unchanged from the original ``metrics.py`` module; the
refactor moves the primitives onto a class implementing the
``MetricCalculator`` Protocol so swap is meaningful end-to-end at
both the per-query surface and the per-strategy aggregation surface.
Bit-identity is verified at S41 commit 11 by replaying S40b's run
``c168c2ba`` through the refactored class.

Edge cases preserved verbatim from the original implementation:

- empty ``expected`` returns 0.0 (recall, precision) and
  ``Decimal("0.0000")`` (MRR); the entry would not have passed
  ``GoldSetEntry`` validation but the defence is kept.
- ``k <= 0`` returns 0.0 for recall@k and precision@k.
- precision@k divides by ``min(k, len(returned))`` so a strategy
  returning fewer than k results is not penalised for non-returns.
- latency percentile follows the nearest-rank NIST definition;
  ``ceil(pct/100 * n)``-indexed (1-based).

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
from typing import Iterable, Mapping, Sequence
from uuid import UUID

from contexts.retrieval_evaluation.domain.evaluation_result import (
    SUPPORTED_K_VALUES,
)
from contexts.retrieval_evaluation.domain.metric_calculator import (
    AggregatedMetrics,
    PerQueryMetrics,
)


class BinaryRelevanceMetrics:
    """Default ``MetricCalculator``: binary relevance per D105 (D111 cmt 6)."""

    def compute_per_query(
        self,
        *,
        returned: Sequence[UUID],
        expected: Sequence[UUID],
    ) -> PerQueryMetrics:
        recall = {
            k: self._recall_at_k(returned=returned, expected=expected, k=k)
            for k in SUPPORTED_K_VALUES
        }
        precision = {
            k: self._precision_at_k(returned=returned, expected=expected, k=k)
            for k in SUPPORTED_K_VALUES
        }
        mrr = self._mean_reciprocal_rank(returned=returned, expected=expected)
        return PerQueryMetrics(
            recall_at_k=recall,
            precision_at_k=precision,
            mrr=mrr,
        )

    def aggregate_per_strategy(
        self,
        *,
        per_query_results: Sequence[PerQueryMetrics],
        latencies_ms: Sequence[int],
    ) -> AggregatedMetrics:
        recall_maps = [r.recall_at_k for r in per_query_results]
        precision_maps = [r.precision_at_k for r in per_query_results]
        mrr_values = [r.mrr for r in per_query_results]
        p50, p95, mean_latency = self._latency_percentiles(latencies_ms)
        return AggregatedMetrics(
            recall_at_k_mean=self._mean_per_k(recall_maps),
            precision_at_k_mean=self._mean_per_k(precision_maps),
            mrr_mean=self._mean_mrr(mrr_values),
            latency_ms_p50=p50,
            latency_ms_p95=p95,
            latency_ms_mean=mean_latency,
        )

    @staticmethod
    def _recall_at_k(
        *,
        returned: Sequence[UUID],
        expected: Sequence[UUID],
        k: int,
    ) -> float:
        if not expected or k <= 0:
            return 0.0
        top_k = set(returned[:k])
        hits = sum(1 for chunk_id in expected if chunk_id in top_k)
        return hits / len(expected)

    @staticmethod
    def _precision_at_k(
        *,
        returned: Sequence[UUID],
        expected: Sequence[UUID],
        k: int,
    ) -> float:
        if k <= 0 or not returned or not expected:
            return 0.0
        top_k = list(returned[:k])
        expected_set = set(expected)
        hits = sum(1 for chunk_id in top_k if chunk_id in expected_set)
        return hits / len(top_k)

    @staticmethod
    def _mean_reciprocal_rank(
        *,
        returned: Sequence[UUID],
        expected: Sequence[UUID],
    ) -> Decimal:
        if not returned or not expected:
            return Decimal("0.0000")
        expected_set = set(expected)
        for rank, chunk_id in enumerate(returned, start=1):
            if chunk_id in expected_set:
                value = Decimal(1) / Decimal(rank)
                return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)
        return Decimal("0.0000")

    @staticmethod
    def _mean(values: Iterable[float]) -> float:
        items = list(values)
        if not items:
            return 0.0
        return sum(items) / len(items)

    @classmethod
    def _mean_per_k(
        cls,
        per_query_maps: Sequence[Mapping[int, float]],
    ) -> Mapping[int, float]:
        if not per_query_maps:
            return {k: 0.0 for k in SUPPORTED_K_VALUES}
        return {
            k: cls._mean(m.get(k, 0.0) for m in per_query_maps)
            for k in SUPPORTED_K_VALUES
        }

    @staticmethod
    def _mean_mrr(values: Sequence[Decimal]) -> Decimal:
        if not values:
            return Decimal("0.0000")
        total = sum(values, Decimal("0"))
        avg = total / Decimal(len(values))
        return avg.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)

    @staticmethod
    def _percentile(values: Sequence[int], pct: float) -> int:
        if not values:
            return 0
        if len(values) == 1:
            return int(values[0])
        sorted_values = sorted(values)
        n = len(sorted_values)
        rank = max(1, int(-(-pct * n // 100)))
        rank = min(rank, n)
        return int(sorted_values[rank - 1])

    @classmethod
    def _latency_percentiles(
        cls,
        values: Sequence[int],
    ) -> tuple[int, int, int]:
        if not values:
            return (0, 0, 0)
        p50 = cls._percentile(values, 50.0)
        p95 = cls._percentile(values, 95.0)
        mean = int(round(sum(values) / len(values)))
        return (p50, p95, mean)


__all__ = [
    "BinaryRelevanceMetrics",
]
