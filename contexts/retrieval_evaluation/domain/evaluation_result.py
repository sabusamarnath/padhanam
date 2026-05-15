"""Per-query-per-strategy evaluation result value object (D110 commitment 3).

Each ``EvaluationResult`` captures the outcome of running one
gold-set entry against one retrieval strategy: the ranked
``returned_chunk_ids`` the strategy produced, the per-k accuracy
metrics (recall@k, precision@k at k of 1/3/5/10), the reciprocal-rank
metric (MRR), and the wall-clock latency.

Per D110 commitment 3 these records are append-only and immutable;
if metric formulas change, a new ``EvaluationRun`` lands rather than
revising existing rows per D31 and per D110 alternative (g).

The ``retrieval_strategy`` field carries the canonical identifier
per D110 commitment 6 (``vector_only`` or ``graph_only`` at S40); the
runner's strategy-key projection module
(``application/strategy_keys.py``) converts canonical identifier to
the adapter-dispatch mapping before invoking the agent-level
``AgentRetrievalClientAdapter``.

Domain code is framework-free per D16 — stdlib dataclasses only.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping
from uuid import UUID

# k values per D110 commitment 3
SUPPORTED_K_VALUES: tuple[int, ...] = (1, 3, 5, 10)


@dataclass(frozen=True)
class EvaluationResult:
    """One per-query-per-strategy result row.

    ``recall_at_k`` and ``precision_at_k`` carry the per-k computed
    metrics as plain ``Mapping[int, float]`` keyed by k; the
    repository adapter renders to JSONB at persistence time.

    ``mrr`` is the reciprocal-rank of the first correct chunk in
    ``returned_chunk_ids`` against the entry's
    ``expected_chunk_ids``; the domain helpers at ``metrics.py``
    compute the value.

    ``latency_ms`` captures wall-clock from retrieval-client
    invocation-start to result-return per D110 commitment 3 (no OTel
    span integration at S40 per S40 pre-write reconciliation Finding 5
    autonomous resolution).
    """

    id: UUID
    evaluation_run_id: UUID
    gold_set_entry_id: UUID
    retrieval_strategy: str
    returned_chunk_ids: tuple[UUID, ...]
    recall_at_k: Mapping[int, float]
    precision_at_k: Mapping[int, float]
    mrr: Decimal
    latency_ms: int

    def __post_init__(self) -> None:
        if not self.retrieval_strategy.strip():
            raise ValueError("retrieval_strategy must be non-empty")
        if self.latency_ms < 0:
            raise ValueError(
                f"latency_ms must be non-negative, got {self.latency_ms}"
            )
        if not (Decimal("0") <= self.mrr <= Decimal("1")):
            raise ValueError(
                f"mrr must be in [0, 1], got {self.mrr}"
            )
        for label, mapping in (
            ("recall_at_k", self.recall_at_k),
            ("precision_at_k", self.precision_at_k),
        ):
            missing = set(SUPPORTED_K_VALUES) - set(mapping.keys())
            if missing:
                raise ValueError(
                    f"{label} missing keys: "
                    f"{sorted(missing)} (expected {list(SUPPORTED_K_VALUES)})"
                )
            for k, value in mapping.items():
                if not (0.0 <= value <= 1.0):
                    raise ValueError(
                        f"{label}[{k}] must be in [0, 1], got {value}"
                    )
