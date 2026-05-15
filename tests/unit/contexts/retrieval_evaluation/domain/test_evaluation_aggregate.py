"""Domain value-object tests for EvaluationAggregate (D110)."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from contexts.retrieval_evaluation.domain import (
    SUPPORTED_K_VALUES,
    EvaluationAggregate,
)


def _per_k(value: float = 0.5) -> dict[int, float]:
    return {k: value for k in SUPPORTED_K_VALUES}


def test_construct_aggregate() -> None:
    aggregate = EvaluationAggregate(
        id=uuid4(),
        evaluation_run_id=uuid4(),
        retrieval_strategy="vector_only",
        recall_at_k_mean=_per_k(0.42),
        precision_at_k_mean=_per_k(0.21),
        mrr_mean=Decimal("0.4200"),
        latency_ms_p50=50,
        latency_ms_p95=120,
        latency_ms_mean=70,
    )
    assert aggregate.retrieval_strategy == "vector_only"
    assert aggregate.latency_ms_p50 == 50


def test_negative_latency_rejects() -> None:
    with pytest.raises(ValueError, match="latency_ms_p50"):
        EvaluationAggregate(
            id=uuid4(),
            evaluation_run_id=uuid4(),
            retrieval_strategy="vector_only",
            recall_at_k_mean=_per_k(),
            precision_at_k_mean=_per_k(),
            mrr_mean=Decimal("0.5000"),
            latency_ms_p50=-1,
            latency_ms_p95=120,
            latency_ms_mean=70,
        )


def test_out_of_range_recall_mean_rejects() -> None:
    bad = _per_k(0.5) | {3: -0.1}
    with pytest.raises(ValueError, match="recall_at_k_mean"):
        EvaluationAggregate(
            id=uuid4(),
            evaluation_run_id=uuid4(),
            retrieval_strategy="vector_only",
            recall_at_k_mean=bad,
            precision_at_k_mean=_per_k(),
            mrr_mean=Decimal("0.5000"),
            latency_ms_p50=50,
            latency_ms_p95=120,
            latency_ms_mean=70,
        )


def test_out_of_range_mrr_mean_rejects() -> None:
    with pytest.raises(ValueError, match="mrr_mean"):
        EvaluationAggregate(
            id=uuid4(),
            evaluation_run_id=uuid4(),
            retrieval_strategy="vector_only",
            recall_at_k_mean=_per_k(),
            precision_at_k_mean=_per_k(),
            mrr_mean=Decimal("1.5"),
            latency_ms_p50=50,
            latency_ms_p95=120,
            latency_ms_mean=70,
        )


def test_empty_strategy_rejects() -> None:
    with pytest.raises(ValueError, match="retrieval_strategy"):
        EvaluationAggregate(
            id=uuid4(),
            evaluation_run_id=uuid4(),
            retrieval_strategy="",
            recall_at_k_mean=_per_k(),
            precision_at_k_mean=_per_k(),
            mrr_mean=Decimal("0.5000"),
            latency_ms_p50=50,
            latency_ms_p95=120,
            latency_ms_mean=70,
        )
