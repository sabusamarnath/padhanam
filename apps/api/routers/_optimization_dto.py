"""Pydantic request and response DTOs for the optimization HTTP routes (D112, S42).

Mirrors the flat-module convention from the existing router surfaces
(``_run_history_dto.py``, ``_audit_dto.py``, ``_ingestion_dto.py``). The
domain dataclasses pass through ``model_validate`` cleanly via
``ConfigDict(from_attributes=True)``.

Three surfaces ship at S42:

- Optimization runs: ``POST /optimization-runs``,
  ``GET /optimization-runs``, ``GET /optimization-runs/{id}``.
- Recommendations: ``GET /recommendations``,
  ``GET /recommendations/{id}``.
- Recommendation lifecycle: ``POST /recommendations/{id}/acknowledge``,
  ``POST /recommendations/{id}/apply``,
  ``POST /recommendations/{id}/reject``. The actor for each transition
  comes from the JWT principal at the route handler; the request body
  is empty.

Evidence-citation discriminated union (D111 commitment 7 / D112
commitment 2):

The domain union is dispatched on
``RecommendationCategory`` (a ``str, Enum``). The Pydantic mirror
declares a ``Literal[<category-value>]`` discriminator field on each
variant and binds them with ``Annotated[Union[...], Discriminator]``;
``model_validate`` on a domain object reads the ``category`` property
(which returns the enum, which equals the matching literal string via
the str-Enum mixin) and selects the variant. The wire shape matches
``citation_to_dict()`` output so HTTP, JSONB storage, and audit-event
payloads share one canonical shape.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Discriminator, Field


# ---------------------------------------------------------------------------
# Evidence citation discriminated union
# ---------------------------------------------------------------------------


class CaveatAnnotationResponse(BaseModel):
    """Mirrors ``CaveatAnnotation`` 1:1 per D111 commitment 7."""

    model_config = ConfigDict(from_attributes=True)

    strategy_id: str
    state: str
    caveat_code: str


class StrategyComparisonResponse(BaseModel):
    """Mirrors ``StrategyComparison`` 1:1 per D111 commitment 7."""

    model_config = ConfigDict(from_attributes=True)

    strategy_a: str
    strategy_b: str
    recall_at_k_delta: dict[int, float]
    precision_at_k_delta: dict[int, float]


class RetrievalStrategyCitationResponse(BaseModel):
    """Evidence citation for ``retrieval_strategy`` recommendations."""

    model_config = ConfigDict(from_attributes=True)

    category: Literal["retrieval_strategy"] = "retrieval_strategy"
    evaluation_run_id: UUID
    gold_set_id: UUID
    comparison: StrategyComparisonResponse
    caveats: list[CaveatAnnotationResponse] = Field(default_factory=list)


class CostAggregateResponse(BaseModel):
    """Mirrors ``CostAggregate`` 1:1 per D111 commitment 7."""

    model_config = ConfigDict(from_attributes=True)

    agent_template_id: UUID
    mean_cost_per_successful_task_usd: Decimal
    time_window_start: datetime
    time_window_end: datetime
    n_successful_runs: int
    n_runs_total: int


class CostOptimizationCitationResponse(BaseModel):
    """Evidence citation for ``cost_optimization`` recommendations."""

    model_config = ConfigDict(from_attributes=True)

    category: Literal["cost_optimization"] = "cost_optimization"
    run_history_record_ids: list[UUID]
    cost_aggregate: CostAggregateResponse


EvidenceCitationResponse = Annotated[
    Union[
        RetrievalStrategyCitationResponse,
        CostOptimizationCitationResponse,
    ],
    Discriminator("category"),
]


# ---------------------------------------------------------------------------
# Recommendation aggregate
# ---------------------------------------------------------------------------


class RecommendationResponse(BaseModel):
    """Mirrors ``Recommendation`` 1:1 per D111 commitment 3.

    The ``evidence_citations`` field carries the discriminated union;
    each item's ``category`` discriminator selects the variant the
    Phase 2 UX consumer renders.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    jurisdiction: str
    category: str
    subject: str
    text: str
    evidence_citations: list[EvidenceCitationResponse]
    status: str
    generated_at: datetime
    generated_by_run_id: UUID
    last_transition_at: datetime
    last_transition_by_user_id: str | None


class RecommendationListResponse(BaseModel):
    """Envelope for ``GET /recommendations``."""

    items: list[RecommendationResponse]
    next_cursor: str | None = None


# ---------------------------------------------------------------------------
# Optimization run
# ---------------------------------------------------------------------------


class CategorySkipReasonResponse(BaseModel):
    """Mirrors ``CategorySkipReason`` 1:1 per D111 commitment 2.

    Structured skip-reason captured on the optimization run aggregate
    when a rule's substrate is unavailable (Phase 1: model_choice and
    prompt_revision).
    """

    model_config = ConfigDict(from_attributes=True)

    reason_code: str
    reason_text: str


class OptimizationRunResponse(BaseModel):
    """Mirrors ``OptimizationRun`` 1:1 per D111 commitment 2."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    jurisdiction: str
    invoked_by_user_id: str
    invoked_at: datetime
    completed_at: datetime | None
    status: str
    skipped_categories: dict[str, CategorySkipReasonResponse] = Field(
        default_factory=dict
    )


class StartOptimizationRunResponse(BaseModel):
    """Response body for ``POST /optimization-runs``.

    Synchronous kickoff (Finding 3 / D112 commitment 4): the route
    blocks until the engine completes and returns the run aggregate
    with every generated recommendation embedded plus the structured
    skip-reasons captured during rule iteration.
    """

    run: OptimizationRunResponse
    recommendations: list[RecommendationResponse]


class OptimizationRunListResponse(BaseModel):
    """Envelope for ``GET /optimization-runs``."""

    items: list[OptimizationRunResponse]
    next_cursor: str | None = None


# ---------------------------------------------------------------------------
# Recommendation lifecycle
# ---------------------------------------------------------------------------


class RecommendationStatusTransitionResponse(BaseModel):
    """Mirrors ``RecommendationStatusTransition`` 1:1 per D111 commitment 4."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recommendation_id: UUID
    from_status: str
    to_status: str
    transitioned_by_user_id: str
    transitioned_at: datetime


class TransitionResponse(BaseModel):
    """Response body for the three lifecycle transition routes.

    Acknowledge / apply / reject share the shape: the updated
    recommendation aggregate plus the canonical transition row from
    ``recommendation_status_transitions``.
    """

    recommendation: RecommendationResponse
    transition: RecommendationStatusTransitionResponse


__all__ = [
    "CategorySkipReasonResponse",
    "CaveatAnnotationResponse",
    "CostAggregateResponse",
    "CostOptimizationCitationResponse",
    "EvidenceCitationResponse",
    "OptimizationRunListResponse",
    "OptimizationRunResponse",
    "RecommendationListResponse",
    "RecommendationResponse",
    "RecommendationStatusTransitionResponse",
    "RetrievalStrategyCitationResponse",
    "StartOptimizationRunResponse",
    "StrategyComparisonResponse",
    "TransitionResponse",
]
