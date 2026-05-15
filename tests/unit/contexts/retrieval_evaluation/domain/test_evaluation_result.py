"""Domain value-object tests for EvaluationResult (D110)."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from contexts.retrieval_evaluation.domain import (
    SUPPORTED_K_VALUES,
    EvaluationResult,
)


def _per_k(value: float = 0.5) -> dict[int, float]:
    return {k: value for k in SUPPORTED_K_VALUES}


def test_construct_with_full_per_k_maps() -> None:
    chunk_id = uuid4()
    result = EvaluationResult(
        id=uuid4(),
        evaluation_run_id=uuid4(),
        gold_set_entry_id=uuid4(),
        retrieval_strategy="vector_only",
        returned_chunk_ids=(chunk_id,),
        recall_at_k=_per_k(0.5),
        precision_at_k=_per_k(0.25),
        mrr=Decimal("0.5000"),
        latency_ms=42,
    )
    assert result.retrieval_strategy == "vector_only"


def test_missing_k_key_rejects() -> None:
    incomplete = {1: 0.5, 3: 0.5, 5: 0.5}  # missing k=10
    with pytest.raises(ValueError, match="recall_at_k missing keys"):
        EvaluationResult(
            id=uuid4(),
            evaluation_run_id=uuid4(),
            gold_set_entry_id=uuid4(),
            retrieval_strategy="vector_only",
            returned_chunk_ids=(uuid4(),),
            recall_at_k=incomplete,
            precision_at_k=_per_k(),
            mrr=Decimal("0.5000"),
            latency_ms=42,
        )


def test_out_of_range_recall_rejects() -> None:
    bad = _per_k(0.5) | {1: 1.5}
    with pytest.raises(ValueError, match="recall_at_k"):
        EvaluationResult(
            id=uuid4(),
            evaluation_run_id=uuid4(),
            gold_set_entry_id=uuid4(),
            retrieval_strategy="vector_only",
            returned_chunk_ids=(uuid4(),),
            recall_at_k=bad,
            precision_at_k=_per_k(),
            mrr=Decimal("0.5000"),
            latency_ms=42,
        )


def test_negative_latency_rejects() -> None:
    with pytest.raises(ValueError, match="latency_ms"):
        EvaluationResult(
            id=uuid4(),
            evaluation_run_id=uuid4(),
            gold_set_entry_id=uuid4(),
            retrieval_strategy="vector_only",
            returned_chunk_ids=(uuid4(),),
            recall_at_k=_per_k(),
            precision_at_k=_per_k(),
            mrr=Decimal("0.5000"),
            latency_ms=-1,
        )


def test_out_of_range_mrr_rejects() -> None:
    with pytest.raises(ValueError, match="mrr must be in"):
        EvaluationResult(
            id=uuid4(),
            evaluation_run_id=uuid4(),
            gold_set_entry_id=uuid4(),
            retrieval_strategy="vector_only",
            returned_chunk_ids=(uuid4(),),
            recall_at_k=_per_k(),
            precision_at_k=_per_k(),
            mrr=Decimal("1.5000"),
            latency_ms=10,
        )


def test_empty_strategy_rejects() -> None:
    with pytest.raises(ValueError, match="retrieval_strategy"):
        EvaluationResult(
            id=uuid4(),
            evaluation_run_id=uuid4(),
            gold_set_entry_id=uuid4(),
            retrieval_strategy="   ",
            returned_chunk_ids=(uuid4(),),
            recall_at_k=_per_k(),
            precision_at_k=_per_k(),
            mrr=Decimal("0.5000"),
            latency_ms=10,
        )
