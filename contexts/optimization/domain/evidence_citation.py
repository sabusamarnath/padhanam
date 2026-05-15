"""Evidence citation discriminated union (D111 commitment 7).

Each recommendation category commits to a specific citation shape.
Phase 1 ships two concrete shapes:

- ``RetrievalStrategyEvidenceCitation`` for the retrieval_strategy
  category: evaluation_run_id + gold_set_id + per-k delta tables at
  all four k values + optional structured caveat annotations.
- ``CostOptimizationEvidenceCitation`` for the cost_optimization
  category: run_history_record_ids + cost aggregate by
  agent_template_id over a time window.

Phase 2 categories (model_choice, prompt_revision) activate when
their substrate ships (scoring-sheet evaluation runs from
contexts/evaluation/); their citation shapes land at that session.

Caveat fields are structured (queryable downstream) not free-form
prose per D111 commitment 7. The CaveatAnnotation carries a
``caveat_code`` that procurement readers can filter on; Phase 2 may
add new caveat_code values without schema migration since this
lives in JSONB at the storage layer.

Domain code is framework-free per D16 — stdlib dataclasses only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Mapping
from uuid import UUID

from contexts.optimization.domain.category import RecommendationCategory


# Caveat code vocabulary. Stable identifiers procurement readers can
# filter on; new codes add at substrate-evolution time without
# breaking existing consumers because storage is JSONB.
CAVEAT_INFRASTRUCTURE_SUBSTRATE_CHECK_REQUIRED: str = (
    "infrastructure_substrate_check_required"
)


@dataclass(frozen=True)
class CaveatAnnotation:
    """Structured caveat on an evidence citation (D111 commitment 7).

    Example values: ``strategy_id="graph_only"``,
    ``state="all_zero_aggregates"``,
    ``caveat_code="infrastructure_substrate_check_required"`` (the
    S40b graph_only case under the graph-extract pipeline reliability
    deviation).
    """

    strategy_id: str
    state: str
    caveat_code: str

    def __post_init__(self) -> None:
        if not self.strategy_id.strip():
            raise ValueError("strategy_id must be non-empty")
        if not self.state.strip():
            raise ValueError("state must be non-empty")
        if not self.caveat_code.strip():
            raise ValueError("caveat_code must be non-empty")


@dataclass(frozen=True)
class StrategyComparison:
    """The compared-strategies surface on retrieval_strategy citations."""

    strategy_a: str
    strategy_b: str
    recall_at_k_delta: Mapping[int, float]
    precision_at_k_delta: Mapping[int, float]


@dataclass(frozen=True)
class RetrievalStrategyEvidenceCitation:
    """Evidence citation for retrieval_strategy recommendations.

    Cites a specific evaluation run plus gold set; the comparison
    surface carries deltas at all four k values per the S40b verdict
    that recall@k differentials are the load-bearing procurement-grade
    surface. Caveats carry structured annotations when a compared
    strategy's aggregates are all-zeros (e.g. graph_only at S40b
    under the graph-extract pipeline reliability deviation).
    """

    evaluation_run_id: UUID
    gold_set_id: UUID
    comparison: StrategyComparison
    caveats: tuple[CaveatAnnotation, ...] = ()

    @property
    def category(self) -> RecommendationCategory:
        return RecommendationCategory.RETRIEVAL_STRATEGY


@dataclass(frozen=True)
class CostAggregate:
    """The cost-aggregate surface on cost_optimization citations.

    Rolls up by agent_template_id per D111 commitment 5 reasoning:
    RunRecord per S31 D95 carries agent_template_id and
    total_cost_usd but not model_id; aggregation by template is the
    structurally honest cut at Phase 1 substrate. Model rollup is a
    Phase 2 promotion if recommendation evidence demands.
    """

    agent_template_id: UUID
    mean_cost_per_successful_task_usd: Decimal
    time_window_start: datetime
    time_window_end: datetime
    n_successful_runs: int
    n_runs_total: int


@dataclass(frozen=True)
class CostOptimizationEvidenceCitation:
    """Evidence citation for cost_optimization recommendations."""

    run_history_record_ids: tuple[UUID, ...]
    cost_aggregate: CostAggregate

    @property
    def category(self) -> RecommendationCategory:
        return RecommendationCategory.COST_OPTIMIZATION


# Phase 1 evidence-citation union. Phase 2 adds the model_choice and
# prompt_revision variants when their substrate ships.
EvidenceCitation = (
    RetrievalStrategyEvidenceCitation | CostOptimizationEvidenceCitation
)


__all__ = [
    "CAVEAT_INFRASTRUCTURE_SUBSTRATE_CHECK_REQUIRED",
    "CaveatAnnotation",
    "CostAggregate",
    "CostOptimizationEvidenceCitation",
    "EvidenceCitation",
    "RetrievalStrategyEvidenceCitation",
    "StrategyComparison",
]
