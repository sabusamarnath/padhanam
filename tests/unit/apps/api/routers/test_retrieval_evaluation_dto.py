"""Unit tests for the retrieval-evaluation HTTP DTOs (D112, S42).

Verify model_validate round-trips from domain dataclasses, Pydantic v2
tuple-to-list serialisation, Decimal-as-string serialisation for MRR,
and the snapshot envelope shapes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from apps.api.routers._retrieval_evaluation_dto import (
    AppendEntryResponse,
    CreateGoldSetResponse,
    EvaluationAggregateResponse,
    EvaluationResultResponse,
    EvaluationRunResponse,
    EvaluationRunSnapshotResponse,
    FinalizeRevisionResponse,
    GoldSetEntryResponse,
    GoldSetListResponse,
    GoldSetResponse,
    GoldSetRevisionResponse,
    GoldSetWithRevisionResponse,
    RetrievalCandidateResponse,
    RetrievalCandidatesResponse,
    StartEvaluationRunResponse,
)
from contexts.ingestion.domain.chunk_result import ChunkResult
from contexts.retrieval_evaluation.domain import (
    EvaluationAggregate,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunStatus,
    GoldSet,
    GoldSetEntry,
    GoldSetRevision,
    GoldSetRevisionStatus,
)


_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc)
_TENANT_UUID = UUID("00000000-0000-4000-8000-00000000a001")
_JURISDICTION = "eu-west"


def _make_gold_set(current_revision_id: UUID | None = None) -> GoldSet:
    return GoldSet(
        id=uuid4(),
        tenant_id=_TENANT_UUID,
        jurisdiction=_JURISDICTION,
        name="P11 retrieval baseline",
        created_by_user_id="cli-operator",
        created_at=_NOW,
        current_revision_id=current_revision_id,
    )


def _make_draft_revision(gold_set_id: UUID) -> GoldSetRevision:
    return GoldSetRevision(
        id=uuid4(),
        gold_set_id=gold_set_id,
        revision_number=1,
        status=GoldSetRevisionStatus.DRAFT,
        created_by_user_id="cli-operator",
        created_at=_NOW,
        finalized_at=None,
        this_event_hash=None,
        previous_event_hash=None,
    )


def _make_finalized_revision(gold_set_id: UUID) -> GoldSetRevision:
    return GoldSetRevision(
        id=uuid4(),
        gold_set_id=gold_set_id,
        revision_number=1,
        status=GoldSetRevisionStatus.FINALIZED,
        created_by_user_id="cli-operator",
        created_at=_NOW,
        finalized_at=_NOW,
        this_event_hash="a" * 64,
        previous_event_hash="0" * 64,
    )


def _make_entry(revision_id: UUID, index: int = 0) -> GoldSetEntry:
    return GoldSetEntry(
        id=uuid4(),
        gold_set_revision_id=revision_id,
        entry_index=index,
        query="What is LVT?",
        expected_chunk_ids=(uuid4(), uuid4()),
    )


def _make_chunk_result() -> ChunkResult:
    return ChunkResult(
        chunk_id=uuid4(),
        source_id=uuid4(),
        tenant_id=str(_TENANT_UUID),
        jurisdiction=_JURISDICTION,
        content="LVT decomposes a vision into hypotheses.",
        structural_metadata={"heading": "Introduction"},
        similarity_score=0.872,
        created_at=_NOW,
        chunk_index=3,
        source_snapshot={"file_name": "lvt_overview.md", "file_type": "markdown"},
    )


def _make_evaluation_run(gold_set_id: UUID, revision_id: UUID) -> EvaluationRun:
    return EvaluationRun(
        id=uuid4(),
        tenant_id=_TENANT_UUID,
        jurisdiction=_JURISDICTION,
        gold_set_id=gold_set_id,
        gold_set_revision_id=revision_id,
        invoked_by_user_id="cli-operator",
        invoked_at=_NOW,
        completed_at=_NOW.replace(second=30),
        status=EvaluationRunStatus.COMPLETED,
    )


def _make_evaluation_result(run_id: UUID, entry_id: UUID) -> EvaluationResult:
    return EvaluationResult(
        id=uuid4(),
        evaluation_run_id=run_id,
        gold_set_entry_id=entry_id,
        retrieval_strategy="vector_only",
        returned_chunk_ids=(uuid4(), uuid4(), uuid4()),
        recall_at_k={1: 1.0, 3: 1.0, 5: 1.0, 10: 1.0},
        precision_at_k={1: 1.0, 3: 0.667, 5: 0.4, 10: 0.2},
        mrr=Decimal("1.0"),
        latency_ms=42,
    )


def _make_evaluation_aggregate(run_id: UUID) -> EvaluationAggregate:
    return EvaluationAggregate(
        id=uuid4(),
        evaluation_run_id=run_id,
        retrieval_strategy="vector_only",
        recall_at_k_mean={1: 0.55, 3: 0.8, 5: 0.867, 10: 1.0},
        precision_at_k_mean={1: 0.55, 3: 0.3, 5: 0.2, 10: 0.1},
        mrr_mean=Decimal("0.66"),
        latency_ms_p50=45,
        latency_ms_p95=120,
        latency_ms_mean=58,
    )


# ---------------------------------------------------------------------------
# Gold-set DTOs
# ---------------------------------------------------------------------------


def test_gold_set_response_validates_domain_object() -> None:
    gold_set = _make_gold_set(current_revision_id=uuid4())
    response = GoldSetResponse.model_validate(gold_set)
    assert response.id == gold_set.id
    assert response.tenant_id == gold_set.tenant_id
    assert response.jurisdiction == gold_set.jurisdiction
    assert response.name == gold_set.name
    assert response.created_at == gold_set.created_at
    assert response.current_revision_id == gold_set.current_revision_id


def test_gold_set_response_allows_null_current_revision_id() -> None:
    gold_set = _make_gold_set(current_revision_id=None)
    response = GoldSetResponse.model_validate(gold_set)
    assert response.current_revision_id is None
    payload = json.loads(response.model_dump_json())
    assert payload["current_revision_id"] is None


def test_gold_set_revision_response_validates_finalized() -> None:
    revision = _make_finalized_revision(uuid4())
    response = GoldSetRevisionResponse.model_validate(revision)
    assert response.status == "finalized"
    assert response.this_event_hash == "a" * 64
    assert response.previous_event_hash == "0" * 64
    assert response.finalized_at == _NOW


def test_gold_set_revision_response_validates_draft() -> None:
    revision = _make_draft_revision(uuid4())
    response = GoldSetRevisionResponse.model_validate(revision)
    assert response.status == "draft"
    assert response.finalized_at is None
    assert response.this_event_hash is None
    assert response.previous_event_hash is None


def test_gold_set_entry_response_serializes_tuple_as_list() -> None:
    entry = _make_entry(uuid4())
    response = GoldSetEntryResponse.model_validate(entry)
    assert isinstance(response.expected_chunk_ids, list)
    assert len(response.expected_chunk_ids) == 2
    assert response.query == entry.query


def test_gold_set_with_revision_response_carries_entries() -> None:
    gold_set = _make_gold_set(current_revision_id=uuid4())
    revision = _make_finalized_revision(gold_set.id)
    entries = (_make_entry(revision.id, 0), _make_entry(revision.id, 1))
    response = GoldSetWithRevisionResponse(
        gold_set=GoldSetResponse.model_validate(gold_set),
        current_revision=GoldSetRevisionResponse.model_validate(revision),
        entries=[GoldSetEntryResponse.model_validate(e) for e in entries],
    )
    assert len(response.entries) == 2
    assert response.current_revision is not None


def test_gold_set_with_revision_response_allows_null_revision() -> None:
    gold_set = _make_gold_set(current_revision_id=None)
    response = GoldSetWithRevisionResponse(
        gold_set=GoldSetResponse.model_validate(gold_set),
        current_revision=None,
        entries=[],
    )
    assert response.current_revision is None
    assert response.entries == []


def test_create_gold_set_response_envelope() -> None:
    gold_set = _make_gold_set()
    revision = _make_draft_revision(gold_set.id)
    response = CreateGoldSetResponse(
        gold_set=GoldSetResponse.model_validate(gold_set),
        initial_revision=GoldSetRevisionResponse.model_validate(revision),
    )
    assert response.gold_set.id == gold_set.id
    assert response.initial_revision.status == "draft"


def test_append_entry_response_envelope() -> None:
    revision = _make_draft_revision(uuid4())
    entry = _make_entry(revision.id, 0)
    response = AppendEntryResponse(
        revision=GoldSetRevisionResponse.model_validate(revision),
        entry=GoldSetEntryResponse.model_validate(entry),
        opened_new_draft=True,
    )
    assert response.opened_new_draft is True
    assert response.entry.entry_index == 0


def test_finalize_revision_response_envelope() -> None:
    revision = _make_finalized_revision(uuid4())
    response = FinalizeRevisionResponse(
        revision=GoldSetRevisionResponse.model_validate(revision),
        this_event_hash=revision.this_event_hash,
        previous_event_hash=revision.previous_event_hash,
    )
    assert response.this_event_hash == "a" * 64


def test_gold_set_list_response_with_next_cursor() -> None:
    items = [GoldSetResponse.model_validate(_make_gold_set()) for _ in range(3)]
    response = GoldSetListResponse(items=items, next_cursor="opaque-b64")
    assert len(response.items) == 3
    assert response.next_cursor == "opaque-b64"


def test_gold_set_list_response_empty_with_no_cursor() -> None:
    response = GoldSetListResponse(items=[], next_cursor=None)
    payload = json.loads(response.model_dump_json())
    assert payload == {"items": [], "next_cursor": None}


# ---------------------------------------------------------------------------
# Retrieval candidates
# ---------------------------------------------------------------------------


def test_retrieval_candidate_response_validates_chunk_result() -> None:
    chunk = _make_chunk_result()
    response = RetrievalCandidateResponse.model_validate(chunk)
    assert response.chunk_id == chunk.chunk_id
    assert response.source_id == chunk.source_id
    assert response.similarity_score == 0.872
    assert response.content == chunk.content
    assert response.chunk_index == 3
    assert response.source_snapshot["file_name"] == "lvt_overview.md"


def test_retrieval_candidates_response_envelope() -> None:
    chunks = [_make_chunk_result() for _ in range(2)]
    response = RetrievalCandidatesResponse(
        candidates=[
            RetrievalCandidateResponse.model_validate(c) for c in chunks
        ]
    )
    assert len(response.candidates) == 2


# ---------------------------------------------------------------------------
# Evaluation-run DTOs
# ---------------------------------------------------------------------------


def test_evaluation_run_response_validates_domain_object() -> None:
    gold_set_id = uuid4()
    revision_id = uuid4()
    run = _make_evaluation_run(gold_set_id, revision_id)
    response = EvaluationRunResponse.model_validate(run)
    assert response.id == run.id
    assert response.status == "completed"
    assert response.gold_set_id == gold_set_id
    assert response.gold_set_revision_id == revision_id


def test_evaluation_result_response_serializes_decimal_mrr_as_string() -> None:
    result = _make_evaluation_result(uuid4(), uuid4())
    response = EvaluationResultResponse.model_validate(result)
    payload = json.loads(response.model_dump_json())
    assert payload["mrr"] == "1.0"


def test_evaluation_result_response_preserves_per_k_metrics() -> None:
    result = _make_evaluation_result(uuid4(), uuid4())
    response = EvaluationResultResponse.model_validate(result)
    payload = json.loads(response.model_dump_json())
    # Pydantic v2 stringifies int keys at JSON serialisation time.
    assert payload["recall_at_k"] == {"1": 1.0, "3": 1.0, "5": 1.0, "10": 1.0}
    assert payload["precision_at_k"]["3"] == 0.667


def test_evaluation_aggregate_response_validates() -> None:
    run_id = uuid4()
    aggregate = _make_evaluation_aggregate(run_id)
    response = EvaluationAggregateResponse.model_validate(aggregate)
    assert response.retrieval_strategy == "vector_only"
    assert response.latency_ms_p95 == 120
    payload = json.loads(response.model_dump_json())
    assert payload["mrr_mean"] == "0.66"
    assert payload["recall_at_k_mean"]["3"] == 0.8


def test_evaluation_run_snapshot_response_envelope() -> None:
    gold_set_id = uuid4()
    revision_id = uuid4()
    run = _make_evaluation_run(gold_set_id, revision_id)
    result = _make_evaluation_result(run.id, uuid4())
    aggregate = _make_evaluation_aggregate(run.id)
    response = EvaluationRunSnapshotResponse(
        run=EvaluationRunResponse.model_validate(run),
        results=[EvaluationResultResponse.model_validate(result)],
        aggregates=[EvaluationAggregateResponse.model_validate(aggregate)],
    )
    assert response.run.id == run.id
    assert len(response.results) == 1
    assert len(response.aggregates) == 1


def test_start_evaluation_run_response_carries_full_snapshot() -> None:
    gold_set_id = uuid4()
    revision_id = uuid4()
    run = _make_evaluation_run(gold_set_id, revision_id)
    result = _make_evaluation_result(run.id, uuid4())
    aggregate = _make_evaluation_aggregate(run.id)
    response = StartEvaluationRunResponse(
        run=EvaluationRunResponse.model_validate(run),
        results=[EvaluationResultResponse.model_validate(result)],
        aggregates=[EvaluationAggregateResponse.model_validate(aggregate)],
    )
    payload = json.loads(response.model_dump_json())
    assert payload["run"]["status"] == "completed"
    assert len(payload["results"]) == 1
    assert len(payload["aggregates"]) == 1
