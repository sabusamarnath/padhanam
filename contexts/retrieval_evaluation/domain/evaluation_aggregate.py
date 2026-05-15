"""Per-strategy evaluation aggregate value object (D110 commitment 4).

Each ``EvaluationAggregate`` summarises one retrieval strategy's
performance across a run's per-query records: the mean recall@k and
precision@k across entries, the mean MRR, and the latency
percentiles (p50, p95, mean).

Per D110 commitment 4 aggregates compute at run-completion time
from the per-query ``EvaluationResult`` rows via the helpers at
``metrics.py``; aggregation is not on-read because the formula has
to live somewhere and stable evidence at fixed values is what the
optimization layer at S41 cites. Per D110 alternative (g)
aggregates are append-only and immutable like the per-query rows.

The ``retrieval_strategy`` field carries the same canonical
identifier vocabulary as ``EvaluationResult`` per D110 commitment 6.

Domain code is framework-free per D16 — stdlib dataclasses only.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping
from uuid import UUID


@dataclass(frozen=True)
class EvaluationAggregate:
    """One per-strategy aggregate row.

    ``recall_at_k_mean`` and ``precision_at_k_mean`` carry per-k mean
    values across the run's entries for this strategy. ``mrr_mean``
    is the mean reciprocal-rank. Latency percentiles capture the
    distribution shape (p50/p95/mean) per D110 commitment 4.
    """

    id: UUID
    evaluation_run_id: UUID
    retrieval_strategy: str
    recall_at_k_mean: Mapping[int, float]
    precision_at_k_mean: Mapping[int, float]
    mrr_mean: Decimal
    latency_ms_p50: int
    latency_ms_p95: int
    latency_ms_mean: int

    def __post_init__(self) -> None:
        if not self.retrieval_strategy.strip():
            raise ValueError("retrieval_strategy must be non-empty")
        for label, value in (
            ("latency_ms_p50", self.latency_ms_p50),
            ("latency_ms_p95", self.latency_ms_p95),
            ("latency_ms_mean", self.latency_ms_mean),
        ):
            if value < 0:
                raise ValueError(
                    f"{label} must be non-negative, got {value}"
                )
        if not (Decimal("0") <= self.mrr_mean <= Decimal("1")):
            raise ValueError(
                f"mrr_mean must be in [0, 1], got {self.mrr_mean}"
            )
        for label, mapping in (
            ("recall_at_k_mean", self.recall_at_k_mean),
            ("precision_at_k_mean", self.precision_at_k_mean),
        ):
            for k, mean in mapping.items():
                if not (0.0 <= mean <= 1.0):
                    raise ValueError(
                        f"{label}[{k}] must be in [0, 1], got {mean}"
                    )
