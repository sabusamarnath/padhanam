"""Tests for BinaryRelevanceMetrics (default MetricCalculator, D111 cmt 6).

Math-level tests previously at the module-level ``metrics.py`` lift
onto the ``BinaryRelevanceMetrics`` class per the S41 refactor. The
math is unchanged; the test surface mirrors the previous primitive-
level coverage so bit-identity preservation is verifiable at unit-
test granularity.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from contexts.retrieval_evaluation.domain.binary_relevance_metrics import (
    BinaryRelevanceMetrics,
)
from contexts.retrieval_evaluation.domain.metric_calculator import (
    AggregatedMetrics,
    PerQueryMetrics,
)


def _ids(n: int) -> list[UUID]:
    return [uuid4() for _ in range(n)]


def _calc() -> BinaryRelevanceMetrics:
    return BinaryRelevanceMetrics()


# ----------------------------------------------------------------------
# compute_per_query: recall@k
# ----------------------------------------------------------------------


def test_compute_per_query_recall_perfect_top_one() -> None:
    expected = _ids(1)
    returned = list(expected)
    result = _calc().compute_per_query(returned=returned, expected=expected)
    assert result.recall_at_k[1] == 1.0


def test_compute_per_query_recall_partial() -> None:
    expected = _ids(4)
    returned = [expected[0], uuid4(), expected[1], uuid4(), uuid4()]
    result = _calc().compute_per_query(returned=returned, expected=expected)
    # 2 of 4 expected appear in top-5
    assert result.recall_at_k[5] == 0.5


def test_compute_per_query_recall_misses_outside_window() -> None:
    expected = _ids(2)
    returned = [uuid4(), uuid4(), uuid4(), uuid4(), expected[0], expected[1]]
    result = _calc().compute_per_query(returned=returned, expected=expected)
    assert result.recall_at_k[3] == 0.0


def test_compute_per_query_recall_empty_expected() -> None:
    result = _calc().compute_per_query(returned=[uuid4()], expected=[])
    # empty expected returns 0.0 at every k
    assert all(v == 0.0 for v in result.recall_at_k.values())


# ----------------------------------------------------------------------
# compute_per_query: precision@k
# ----------------------------------------------------------------------


def test_compute_per_query_precision_all_correct() -> None:
    expected = _ids(3)
    returned = list(expected)
    result = _calc().compute_per_query(returned=returned, expected=expected)
    assert result.precision_at_k[3] == 1.0


def test_compute_per_query_precision_mixed() -> None:
    expected = _ids(2)
    returned = [expected[0], uuid4(), expected[1], uuid4()]
    result = _calc().compute_per_query(returned=returned, expected=expected)
    # top-3: 2 correct out of 3
    assert result.precision_at_k[3] == 2 / 3


def test_compute_per_query_precision_fewer_returned_than_k() -> None:
    expected = _ids(1)
    returned = list(expected)
    result = _calc().compute_per_query(returned=returned, expected=expected)
    # k=5 but only 1 returned; divides by min(k, len(returned)) → 1.0
    assert result.precision_at_k[5] == 1.0


# ----------------------------------------------------------------------
# compute_per_query: MRR
# ----------------------------------------------------------------------


def test_compute_per_query_mrr_first_position() -> None:
    expected = _ids(2)
    returned = [expected[0], uuid4(), uuid4()]
    result = _calc().compute_per_query(returned=returned, expected=expected)
    assert result.mrr == Decimal("1.0000")


def test_compute_per_query_mrr_third_position() -> None:
    expected = _ids(2)
    returned = [uuid4(), uuid4(), expected[1], expected[0]]
    result = _calc().compute_per_query(returned=returned, expected=expected)
    # first expected hit at rank 3 → 1/3 ≈ 0.3333
    assert result.mrr == Decimal("0.3333")


def test_compute_per_query_mrr_no_hit() -> None:
    expected = _ids(2)
    returned = [uuid4() for _ in range(5)]
    result = _calc().compute_per_query(returned=returned, expected=expected)
    assert result.mrr == Decimal("0.0000")


# ----------------------------------------------------------------------
# compute_per_query: shape and keys
# ----------------------------------------------------------------------


def test_compute_per_query_returns_all_k_keys() -> None:
    expected = _ids(3)
    returned = list(expected) + [uuid4()]
    result = _calc().compute_per_query(returned=returned, expected=expected)
    assert set(result.recall_at_k.keys()) == {1, 3, 5, 10}
    assert set(result.precision_at_k.keys()) == {1, 3, 5, 10}
    # all 3 expected fit in top-3: recall@3 = 1.0
    assert result.recall_at_k[3] == 1.0


def test_compute_per_query_returns_per_query_metrics_instance() -> None:
    result = _calc().compute_per_query(returned=[uuid4()], expected=[uuid4()])
    assert isinstance(result, PerQueryMetrics)


# ----------------------------------------------------------------------
# aggregate_per_strategy
# ----------------------------------------------------------------------


def test_aggregate_per_strategy_empty_inputs() -> None:
    result = _calc().aggregate_per_strategy(per_query_results=[], latencies_ms=[])
    assert isinstance(result, AggregatedMetrics)
    assert result.recall_at_k_mean == {1: 0.0, 3: 0.0, 5: 0.0, 10: 0.0}
    assert result.precision_at_k_mean == {1: 0.0, 3: 0.0, 5: 0.0, 10: 0.0}
    assert result.mrr_mean == Decimal("0.0000")
    assert result.latency_ms_p50 == 0
    assert result.latency_ms_p95 == 0
    assert result.latency_ms_mean == 0


def test_aggregate_per_strategy_averages_recall_and_precision() -> None:
    per_query = [
        PerQueryMetrics(
            recall_at_k={1: 0.0, 3: 0.5, 5: 1.0, 10: 1.0},
            precision_at_k={1: 0.0, 3: 0.0, 5: 0.0, 10: 0.0},
            mrr=Decimal("0.5000"),
        ),
        PerQueryMetrics(
            recall_at_k={1: 1.0, 3: 0.5, 5: 0.0, 10: 0.5},
            precision_at_k={1: 1.0, 3: 1.0, 5: 1.0, 10: 1.0},
            mrr=Decimal("1.0000"),
        ),
    ]
    result = _calc().aggregate_per_strategy(
        per_query_results=per_query, latencies_ms=[]
    )
    assert result.recall_at_k_mean[1] == 0.5
    assert result.recall_at_k_mean[3] == 0.5
    assert result.recall_at_k_mean[5] == 0.5
    assert result.recall_at_k_mean[10] == 0.75
    assert result.precision_at_k_mean[5] == 0.5
    assert result.mrr_mean == Decimal("0.7500")


def test_aggregate_per_strategy_mrr_zero_when_no_results() -> None:
    result = _calc().aggregate_per_strategy(per_query_results=[], latencies_ms=[])
    assert result.mrr_mean == Decimal("0.0000")


def test_aggregate_per_strategy_latency_single_value() -> None:
    result = _calc().aggregate_per_strategy(
        per_query_results=[], latencies_ms=[42]
    )
    assert result.latency_ms_p50 == 42
    assert result.latency_ms_p95 == 42
    assert result.latency_ms_mean == 42


def test_aggregate_per_strategy_latency_distribution() -> None:
    values = list(range(1, 101))  # 1..100
    result = _calc().aggregate_per_strategy(
        per_query_results=[], latencies_ms=values
    )
    # nearest-rank percentile per the NIST definition
    assert result.latency_ms_p50 == 50
    assert result.latency_ms_p95 == 95
    # mean(1..100) = 50.5; ROUND_HALF_EVEN → 50
    assert result.latency_ms_mean == 50
