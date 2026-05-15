"""Retrieval-evaluation metric primitives (D110 commitments 3 and 4).

Per-query metrics (recall@k, precision@k, MRR) and per-strategy
aggregation helpers (mean across entries, latency percentiles).

Custom implementations land at this module per S40 pre-write
reconciliation Finding 4 (no existing metric library to reuse; the
metric definitions are simple and library-free implementations
avoid a dependency for a small surface).

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
from typing import Iterable, Mapping, Sequence
from uuid import UUID

from contexts.retrieval_evaluation.domain.evaluation_result import (
    SUPPORTED_K_VALUES,
)


def recall_at_k(
    *,
    returned: Sequence[UUID],
    expected: Sequence[UUID],
    k: int,
) -> float:
    """Fraction of expected chunks present in the top-k returned.

    Recall@k counts how many expected chunks the strategy surfaced
    within the first k results. Range [0, 1].

    Edge cases:
    - ``expected`` empty: returns 0.0 (the entry would not have
      passed gold-set authoring per ``GoldSetEntry.__post_init__``;
      defensive nonetheless).
    - ``k <= 0``: returns 0.0 (degenerate cut-off).
    - ``k`` exceeds ``len(returned)``: clipped to the available
      results; recall counts hits across whatever surface the
      strategy produced.
    """
    if not expected or k <= 0:
        return 0.0
    top_k = set(returned[:k])
    hits = sum(1 for chunk_id in expected if chunk_id in top_k)
    return hits / len(expected)


def precision_at_k(
    *,
    returned: Sequence[UUID],
    expected: Sequence[UUID],
    k: int,
) -> float:
    """Fraction of top-k returned chunks that are in expected.

    Precision@k counts how many of the strategy's top-k results were
    correct. Divides by ``min(k, len(returned))`` so a strategy that
    returns fewer than k results is not penalised for non-returns:
    precision measures the quality of what was returned, not what
    could have been.

    Edge cases:
    - ``k <= 0``: returns 0.0.
    - ``returned`` empty: returns 0.0 (nothing returned to score).
    - ``expected`` empty: returns 0.0 (defensive; see ``recall_at_k``).
    """
    if k <= 0 or not returned or not expected:
        return 0.0
    top_k = list(returned[:k])
    expected_set = set(expected)
    hits = sum(1 for chunk_id in top_k if chunk_id in expected_set)
    return hits / len(top_k)


def mean_reciprocal_rank(
    *,
    returned: Sequence[UUID],
    expected: Sequence[UUID],
) -> Decimal:
    """Reciprocal of the rank of the first correct chunk in returned.

    For a single query MRR collapses to RR (reciprocal rank): the
    score is ``1/rank`` where ``rank`` is the 1-based position of
    the first expected chunk in ``returned``, or 0 if none of the
    expected chunks surface. Aggregating MRR across queries lives at
    ``aggregate_per_strategy`` below.

    Returns ``Decimal`` quantised to four decimal places to match
    the schema's ``numeric(6,4)`` constraint per
    ``charter/schema.md``.
    """
    if not returned or not expected:
        return Decimal("0.0000")
    expected_set = set(expected)
    for rank, chunk_id in enumerate(returned, start=1):
        if chunk_id in expected_set:
            value = Decimal(1) / Decimal(rank)
            return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)
    return Decimal("0.0000")


def compute_per_k_metrics(
    *,
    returned: Sequence[UUID],
    expected: Sequence[UUID],
) -> tuple[Mapping[int, float], Mapping[int, float]]:
    """Return (recall_at_k, precision_at_k) maps for SUPPORTED_K_VALUES."""
    recall = {k: recall_at_k(returned=returned, expected=expected, k=k) for k in SUPPORTED_K_VALUES}
    precision = {
        k: precision_at_k(returned=returned, expected=expected, k=k)
        for k in SUPPORTED_K_VALUES
    }
    return recall, precision


def _mean(values: Iterable[float]) -> float:
    items = list(values)
    if not items:
        return 0.0
    return sum(items) / len(items)


def _percentile(values: Sequence[int], pct: float) -> int:
    """Nearest-rank percentile (NIST definition).

    For an empty sequence returns 0. For a single value returns that
    value. Otherwise sorts and selects index ``ceil(pct/100 * n) - 1``,
    clamped to ``[0, n-1]``.
    """
    if not values:
        return 0
    if len(values) == 1:
        return int(values[0])
    sorted_values = sorted(values)
    n = len(sorted_values)
    rank = max(1, int(-(-pct * n // 100)))  # ceil(pct/100 * n) via floor-div trick
    rank = min(rank, n)
    return int(sorted_values[rank - 1])


def mean_per_k(
    per_query_maps: Sequence[Mapping[int, float]],
) -> Mapping[int, float]:
    """Mean across queries at each supported k.

    Returns a map keyed by ``SUPPORTED_K_VALUES``; if the input list
    is empty every value is 0.0.
    """
    if not per_query_maps:
        return {k: 0.0 for k in SUPPORTED_K_VALUES}
    return {
        k: _mean(m.get(k, 0.0) for m in per_query_maps)
        for k in SUPPORTED_K_VALUES
    }


def mean_mrr(values: Sequence[Decimal]) -> Decimal:
    """Mean of per-query reciprocal-rank scores, quantised to 4dp."""
    if not values:
        return Decimal("0.0000")
    total = sum(values, Decimal("0"))
    avg = total / Decimal(len(values))
    return avg.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)


def latency_percentiles(
    values: Sequence[int],
) -> tuple[int, int, int]:
    """Return (p50, p95, mean) latency in milliseconds."""
    if not values:
        return (0, 0, 0)
    p50 = _percentile(values, 50.0)
    p95 = _percentile(values, 95.0)
    mean = int(round(sum(values) / len(values)))
    return (p50, p95, mean)
