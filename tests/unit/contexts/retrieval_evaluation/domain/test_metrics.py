"""Tests for retrieval-evaluation metric primitives (D110)."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from contexts.retrieval_evaluation.domain.metrics import (
    compute_per_k_metrics,
    latency_percentiles,
    mean_mrr,
    mean_per_k,
    mean_reciprocal_rank,
    precision_at_k,
    recall_at_k,
)


def _ids(n: int) -> list[UUID]:
    return [uuid4() for _ in range(n)]


def test_recall_at_k_perfect_top_one() -> None:
    expected = _ids(1)
    returned = list(expected)
    assert recall_at_k(returned=returned, expected=expected, k=1) == 1.0


def test_recall_at_k_partial() -> None:
    expected = _ids(4)
    returned = [expected[0], uuid4(), expected[1], uuid4(), uuid4()]
    # 2 of 4 expected appear in top-5
    assert recall_at_k(returned=returned, expected=expected, k=5) == 0.5


def test_recall_at_k_misses_outside_window() -> None:
    expected = _ids(2)
    returned = [uuid4(), uuid4(), uuid4(), uuid4(), expected[0], expected[1]]
    assert recall_at_k(returned=returned, expected=expected, k=3) == 0.0


def test_recall_at_k_empty_expected() -> None:
    assert recall_at_k(returned=[uuid4()], expected=[], k=5) == 0.0


def test_recall_at_k_zero_k() -> None:
    expected = _ids(2)
    assert recall_at_k(returned=expected, expected=expected, k=0) == 0.0


def test_precision_at_k_all_correct() -> None:
    expected = _ids(3)
    returned = list(expected)
    assert precision_at_k(returned=returned, expected=expected, k=3) == 1.0


def test_precision_at_k_mixed() -> None:
    expected = _ids(2)
    returned = [expected[0], uuid4(), expected[1], uuid4()]
    # top-3: 2 correct out of 3
    assert precision_at_k(returned=returned, expected=expected, k=3) == 2 / 3


def test_precision_at_k_fewer_returned_than_k() -> None:
    expected = _ids(1)
    returned = list(expected)
    # k=5 but only 1 returned; divides by 1 (min(k, len(returned))) → 1.0
    assert precision_at_k(returned=returned, expected=expected, k=5) == 1.0


def test_mrr_first_position() -> None:
    expected = _ids(2)
    returned = [expected[0], uuid4(), uuid4()]
    assert mean_reciprocal_rank(returned=returned, expected=expected) == Decimal(
        "1.0000"
    )


def test_mrr_third_position() -> None:
    expected = _ids(2)
    returned = [uuid4(), uuid4(), expected[1], expected[0]]
    # First expected hit at rank 3 → 1/3 ≈ 0.3333
    assert mean_reciprocal_rank(returned=returned, expected=expected) == Decimal(
        "0.3333"
    )


def test_mrr_no_hit() -> None:
    expected = _ids(2)
    returned = [uuid4() for _ in range(5)]
    assert mean_reciprocal_rank(returned=returned, expected=expected) == Decimal(
        "0.0000"
    )


def test_compute_per_k_returns_all_k_keys() -> None:
    expected = _ids(3)
    returned = list(expected) + [uuid4()]
    recall, precision = compute_per_k_metrics(
        returned=returned, expected=expected
    )
    assert set(recall.keys()) == {1, 3, 5, 10}
    assert set(precision.keys()) == {1, 3, 5, 10}
    # All 3 expected fit in top-3: recall@3 = 1.0
    assert recall[3] == 1.0


def test_mean_per_k_empty() -> None:
    result = mean_per_k([])
    assert result == {1: 0.0, 3: 0.0, 5: 0.0, 10: 0.0}


def test_mean_per_k_averages_across_entries() -> None:
    maps = [
        {1: 0.0, 3: 0.5, 5: 1.0, 10: 1.0},
        {1: 1.0, 3: 0.5, 5: 0.0, 10: 0.5},
    ]
    result = mean_per_k(maps)
    assert result[1] == 0.5
    assert result[3] == 0.5
    assert result[5] == 0.5
    assert result[10] == 0.75


def test_mean_mrr_empty() -> None:
    assert mean_mrr([]) == Decimal("0.0000")


def test_mean_mrr_averages() -> None:
    result = mean_mrr([Decimal("1.0000"), Decimal("0.5000"), Decimal("0.0000")])
    assert result == Decimal("0.5000")


def test_latency_percentiles_empty() -> None:
    assert latency_percentiles([]) == (0, 0, 0)


def test_latency_percentiles_single_value() -> None:
    assert latency_percentiles([42]) == (42, 42, 42)


def test_latency_percentiles_distribution() -> None:
    # 100 evenly-spaced values 1..100
    values = list(range(1, 101))
    p50, p95, mean = latency_percentiles(values)
    assert p50 == 50  # nearest-rank ceil(50% * 100) = 50
    assert p95 == 95
    assert mean == 50  # round(5050/100) == 50 (round-half-to-even: 50.5 → 50)
