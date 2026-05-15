"""Pydantic request and response DTOs for the retrieval-evaluation HTTP routes (D112, S42).

Mirrors the flat-module convention from the existing router surfaces
(``_run_history_dto.py``, ``_audit_dto.py``, ``_ingestion_dto.py``). The
domain dataclasses pass through ``model_validate`` cleanly via the
``ConfigDict(from_attributes=True)`` setting; the HTTP boundary
preserves the storage-versus-render discipline from D96 by mirroring
fields without flattening or renaming.

Two surfaces ship at S42:

- Gold-set authoring: ``GET /retrieval-candidates``, ``POST /gold-sets``,
  ``GET /gold-sets``, ``GET /gold-sets/{id}``,
  ``POST /gold-sets/{id}/entries``, ``POST /gold-sets/{id}/finalize``.
  The two-step discovery decomposition preserves the human-in-the-loop
  content-fit selection per D112 commitment 1 (Finding 2 disposition).
- Evaluation runs: ``POST /evaluation-runs``, ``GET /evaluation-runs``,
  ``GET /evaluation-runs/{id}``. Synchronous kickoff per D112 commitment
  4 (Finding 3 disposition).

Pydantic v2 conventions:

- ``model_config = ConfigDict(from_attributes=True)`` so domain
  records pass through ``DTO.model_validate(domain_obj)`` cleanly.
- ``Decimal`` (MRR) serialises as string per the monetary convention
  in ``_run_history_dto`` (the convention generalises to other
  precise-numeric fields).
- ``Mapping[int, float]`` (recall_at_k, precision_at_k) surfaces as
  ``dict[int, float]``; Pydantic v2 stringifies int keys at JSON
  serialisation time, so the wire format is ``{"1": 0.5, ...}``
  matching the domain layer's storage shape.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Retrieval candidates (Stage 1 of the two-step gold-set discovery)
# ---------------------------------------------------------------------------


class RetrievalCandidateResponse(BaseModel):
    """One candidate chunk returned by ``GET /retrieval-candidates``.

    Maps from ``ChunkResult`` (the vector-search result shape) so the
    operator sees ranked chunk_ids plus excerpt content to inform the
    Stage 2 ``POST /gold-sets/{id}/entries`` selection of
    ``expected_chunk_ids``.
    """

    model_config = ConfigDict(from_attributes=True)

    chunk_id: UUID
    source_id: UUID
    similarity_score: float
    content: str
    chunk_index: int
    source_snapshot: dict[str, Any] = Field(default_factory=dict)


class RetrievalCandidatesResponse(BaseModel):
    """Envelope for ``GET /retrieval-candidates``."""

    candidates: list[RetrievalCandidateResponse]


# ---------------------------------------------------------------------------
# Gold-set authoring
# ---------------------------------------------------------------------------


class CreateGoldSetRequest(BaseModel):
    """Request body for ``POST /gold-sets``.

    ``created_by_user_id`` comes from the JWT principal at the route
    handler; the request body only carries the gold-set name.
    """

    name: str = Field(min_length=1)


class GoldSetResponse(BaseModel):
    """Mirrors ``GoldSet`` 1:1 per D109."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    jurisdiction: str
    name: str
    created_by_user_id: str
    created_at: datetime
    current_revision_id: UUID | None


class GoldSetRevisionResponse(BaseModel):
    """Mirrors ``GoldSetRevision`` 1:1 per D109."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    gold_set_id: UUID
    revision_number: int
    status: str
    created_by_user_id: str
    created_at: datetime
    finalized_at: datetime | None
    this_event_hash: str | None
    previous_event_hash: str | None


class GoldSetEntryResponse(BaseModel):
    """Mirrors ``GoldSetEntry`` 1:1 per D109."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    gold_set_revision_id: UUID
    entry_index: int
    query: str
    expected_chunk_ids: list[UUID]


class CreateGoldSetResponse(BaseModel):
    """Response body for ``POST /gold-sets``."""

    gold_set: GoldSetResponse
    initial_revision: GoldSetRevisionResponse


class GoldSetWithRevisionResponse(BaseModel):
    """Response body for ``GET /gold-sets/{id}``.

    Carries the aggregate, the current finalized revision (or null
    when authoring is still in progress on the initial draft), and the
    entries of the current finalized revision when present.
    """

    gold_set: GoldSetResponse
    current_revision: GoldSetRevisionResponse | None
    entries: list[GoldSetEntryResponse] = Field(default_factory=list)


class GoldSetListResponse(BaseModel):
    """Envelope for ``GET /gold-sets`` per D112 cmt 4."""

    items: list[GoldSetResponse]
    next_cursor: str | None = None


class AppendEntryRequest(BaseModel):
    """Request body for ``POST /gold-sets/{id}/entries``."""

    query: str = Field(min_length=1)
    expected_chunk_ids: list[UUID] = Field(min_length=1)


class AppendEntryResponse(BaseModel):
    """Response body for ``POST /gold-sets/{id}/entries``.

    Surfaces ``opened_new_draft`` so the consumer sees when a new
    revision was lazily opened (post-finalize-then-edit case) per
    D109 commitment 6.
    """

    revision: GoldSetRevisionResponse
    entry: GoldSetEntryResponse
    opened_new_draft: bool


class FinalizeRevisionResponse(BaseModel):
    """Response body for ``POST /gold-sets/{id}/finalize``."""

    revision: GoldSetRevisionResponse
    this_event_hash: str
    previous_event_hash: str


# ---------------------------------------------------------------------------
# Evaluation runs
# ---------------------------------------------------------------------------


class StartEvaluationRunRequest(BaseModel):
    """Request body for ``POST /evaluation-runs``.

    ``invoked_by_user_id`` comes from the JWT principal at the route
    handler. ``gold_set_id`` names the gold set to exercise; the run
    pulls the current finalized revision per D110.
    """

    gold_set_id: UUID


class EvaluationRunResponse(BaseModel):
    """Mirrors ``EvaluationRun`` 1:1 per D110."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    jurisdiction: str
    gold_set_id: UUID
    gold_set_revision_id: UUID
    invoked_by_user_id: str
    invoked_at: datetime
    completed_at: datetime | None
    status: str


class EvaluationResultResponse(BaseModel):
    """Mirrors ``EvaluationResult`` 1:1 per D110 commitment 3."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    evaluation_run_id: UUID
    gold_set_entry_id: UUID
    retrieval_strategy: str
    returned_chunk_ids: list[UUID]
    recall_at_k: dict[int, float]
    precision_at_k: dict[int, float]
    mrr: Decimal
    latency_ms: int


class EvaluationAggregateResponse(BaseModel):
    """Mirrors ``EvaluationAggregate`` 1:1 per D110 commitment 4."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    evaluation_run_id: UUID
    retrieval_strategy: str
    recall_at_k_mean: dict[int, float]
    precision_at_k_mean: dict[int, float]
    mrr_mean: Decimal
    latency_ms_p50: int
    latency_ms_p95: int
    latency_ms_mean: int


class EvaluationRunSnapshotResponse(BaseModel):
    """Response body for ``GET /evaluation-runs/{id}``.

    Carries the parent run plus every per-query result plus every
    per-strategy aggregate. Mirrors ``EvaluationRunSnapshot`` from
    the reader port.
    """

    run: EvaluationRunResponse
    results: list[EvaluationResultResponse] = Field(default_factory=list)
    aggregates: list[EvaluationAggregateResponse] = Field(default_factory=list)


class StartEvaluationRunResponse(BaseModel):
    """Response body for ``POST /evaluation-runs``.

    Synchronous kickoff (Finding 3 / D112 commitment 4): the route
    blocks until the run terminates and returns the completed
    snapshot with all per-query results and per-strategy aggregates
    populated.
    """

    run: EvaluationRunResponse
    results: list[EvaluationResultResponse]
    aggregates: list[EvaluationAggregateResponse]


class EvaluationRunListResponse(BaseModel):
    """Envelope for ``GET /evaluation-runs``."""

    items: list[EvaluationRunResponse]
    next_cursor: str | None = None


__all__ = [
    "AppendEntryRequest",
    "AppendEntryResponse",
    "CreateGoldSetRequest",
    "CreateGoldSetResponse",
    "EvaluationAggregateResponse",
    "EvaluationResultResponse",
    "EvaluationRunListResponse",
    "EvaluationRunResponse",
    "EvaluationRunSnapshotResponse",
    "FinalizeRevisionResponse",
    "GoldSetEntryResponse",
    "GoldSetListResponse",
    "GoldSetResponse",
    "GoldSetRevisionResponse",
    "GoldSetWithRevisionResponse",
    "RetrievalCandidateResponse",
    "RetrievalCandidatesResponse",
    "StartEvaluationRunRequest",
    "StartEvaluationRunResponse",
]
