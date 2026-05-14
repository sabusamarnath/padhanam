"""Unit tests for the run-history HTTP response DTOs (S34, D98).

Verify the 1:1 field mirror from domain records, the Pydantic v2
tuple-to-list serialisation, the Decimal-as-string monetary shape,
and the model_validate round-trip from RunRecord (with citations
populated) through RunResponse.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from apps.api.routers._run_history_dto import (
    ChunkCitationResponse,
    EntityCitationResponse,
    RunListResponse,
    RunResponse,
)
from contexts.run_history.domain.citation_records import (
    ChunkCitationRecord,
    EntityCitationRecord,
)
from contexts.run_history.domain.run_record import RunRecord


# --------------------------------------------------------------------
# Fixture helpers.
# --------------------------------------------------------------------


_TENANT_ID = "00000000-0000-4000-8000-00000000a001"
_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)


def _make_chunk_citation(*, run_id: UUID) -> ChunkCitationRecord:
    return ChunkCitationRecord(
        id=uuid4(),
        run_id=run_id,
        chunk_id=uuid4(),
        tenant_id=_TENANT_ID,
        jurisdiction="eu-west",
        chunk_excerpt="Customer interviews surface jobs-to-be-done patterns.",
        source_snapshot={"file_name": "03_customer_interviews.md", "file_type": "markdown"},
    )


def _make_entity_citation(*, run_id: UUID) -> EntityCitationRecord:
    return EntityCitationRecord(
        id=uuid4(),
        run_id=run_id,
        entity_tenant_id=_TENANT_ID,
        entity_name="CustomerInterviews",
        entity_type="Document",
        tenant_id=_TENANT_ID,
        source_chunk_ids=(uuid4(), uuid4()),
    )


def _make_run_record(
    *,
    chunk_citations: tuple[ChunkCitationRecord, ...] = (),
    entity_citations: tuple[EntityCitationRecord, ...] = (),
) -> RunRecord:
    return RunRecord(
        id=uuid4(),
        tenant_id=_TENANT_ID,
        jurisdiction="eu-west",
        agent_template_id=uuid4(),
        agent_template_version=1,
        input_message="What is LVT?",
        output_content="LVT is a Lean Value Tree.",
        started_at=_NOW,
        completed_at=_NOW.replace(second=30),
        termination_reason="content",
        iteration_count=2,
        total_cost_usd=Decimal("0.00123"),
        trace_id=None,
        audit_start_hash="a" * 64,
        audit_end_hash="b" * 64,
        created_at=_NOW.replace(second=30),
        chunk_citations=chunk_citations,
        entity_citations=entity_citations,
    )


# --------------------------------------------------------------------
# RunResponse: 1:1 mirror of RunRecord.
# --------------------------------------------------------------------


def test_run_response_validates_run_record_via_from_attributes() -> None:
    record = _make_run_record()
    response = RunResponse.model_validate(record)
    assert response.id == record.id
    assert response.tenant_id == record.tenant_id
    assert response.jurisdiction == record.jurisdiction
    assert response.agent_template_id == record.agent_template_id
    assert response.agent_template_version == record.agent_template_version
    assert response.input_message == record.input_message
    assert response.output_content == record.output_content
    assert response.started_at == record.started_at
    assert response.completed_at == record.completed_at
    assert response.termination_reason == record.termination_reason
    assert response.iteration_count == record.iteration_count
    assert response.total_cost_usd == record.total_cost_usd
    assert response.trace_id == record.trace_id
    assert response.audit_start_hash == record.audit_start_hash
    assert response.audit_end_hash == record.audit_end_hash
    assert response.created_at == record.created_at
    assert response.chunk_citations == []
    assert response.entity_citations == []


def test_run_response_preserves_citation_tuples_as_lists() -> None:
    """Pydantic v2 default tuple-to-list serialisation per D98."""
    run_id = uuid4()
    chunk = _make_chunk_citation(run_id=run_id)
    entity = _make_entity_citation(run_id=run_id)
    record = _make_run_record(
        chunk_citations=(chunk, chunk),
        entity_citations=(entity,),
    )
    response = RunResponse.model_validate(record)
    assert isinstance(response.chunk_citations, list)
    assert isinstance(response.entity_citations, list)
    assert len(response.chunk_citations) == 2
    assert len(response.entity_citations) == 1
    assert response.chunk_citations[0].id == chunk.id
    assert response.entity_citations[0].id == entity.id


def test_run_response_serialises_decimal_cost_as_string() -> None:
    """Decimal cost surfaces as string per the existing monetary convention."""
    record = _make_run_record()
    response = RunResponse.model_validate(record)
    payload = json.loads(response.model_dump_json())
    assert payload["total_cost_usd"] == "0.00123"


def test_run_response_serialises_datetimes_as_iso_8601() -> None:
    record = _make_run_record()
    response = RunResponse.model_validate(record)
    payload = json.loads(response.model_dump_json())
    assert payload["started_at"] == "2026-05-14T12:00:00Z"
    assert payload["completed_at"] == "2026-05-14T12:00:30Z"


def test_run_response_allows_null_audit_end_hash_for_failed_runs() -> None:
    """RunRecord allows audit_end_hash=None only under termination_reason='failed'."""
    failed = RunRecord(
        id=uuid4(),
        tenant_id=_TENANT_ID,
        jurisdiction="eu-west",
        agent_template_id=uuid4(),
        agent_template_version=1,
        input_message="hi",
        output_content="",
        started_at=_NOW,
        completed_at=_NOW,
        termination_reason="failed",
        iteration_count=0,
        total_cost_usd=Decimal("0"),
        trace_id=None,
        audit_start_hash="c" * 64,
        audit_end_hash=None,
        created_at=_NOW,
    )
    response = RunResponse.model_validate(failed)
    assert response.audit_end_hash is None
    payload = json.loads(response.model_dump_json())
    assert payload["audit_end_hash"] is None


# --------------------------------------------------------------------
# ChunkCitationResponse: 1:1 mirror of ChunkCitationRecord.
# --------------------------------------------------------------------


def test_chunk_citation_response_mirrors_record_fields() -> None:
    run_id = uuid4()
    record = _make_chunk_citation(run_id=run_id)
    response = ChunkCitationResponse.model_validate(record)
    assert response.id == record.id
    assert response.run_id == record.run_id
    assert response.chunk_id == record.chunk_id
    assert response.tenant_id == record.tenant_id
    assert response.jurisdiction == record.jurisdiction
    assert response.chunk_excerpt == record.chunk_excerpt
    assert response.source_snapshot == dict(record.source_snapshot)


def test_chunk_citation_response_allows_null_chunk_id() -> None:
    """The schema's ON DELETE SET NULL behaviour means chunk_id may be None."""
    run_id = uuid4()
    record = ChunkCitationRecord(
        id=uuid4(),
        run_id=run_id,
        chunk_id=None,
        tenant_id=_TENANT_ID,
        jurisdiction="eu-west",
        chunk_excerpt="snapshot-only excerpt",
        source_snapshot={"file_name": "deleted.pdf"},
    )
    response = ChunkCitationResponse.model_validate(record)
    assert response.chunk_id is None


def test_chunk_citation_response_preserves_source_snapshot_keys() -> None:
    run_id = uuid4()
    record = ChunkCitationRecord(
        id=uuid4(),
        run_id=run_id,
        chunk_id=uuid4(),
        tenant_id=_TENANT_ID,
        jurisdiction="eu-west",
        chunk_excerpt="excerpt",
        source_snapshot={
            "file_name": "doc.pdf",
            "file_type": "application/pdf",
            "author": "Casey",
            "extracted_date": "2026-05-14",
        },
    )
    response = ChunkCitationResponse.model_validate(record)
    payload = json.loads(response.model_dump_json())
    assert payload["source_snapshot"]["file_name"] == "doc.pdf"
    assert payload["source_snapshot"]["author"] == "Casey"
    assert payload["source_snapshot"]["extracted_date"] == "2026-05-14"


# --------------------------------------------------------------------
# EntityCitationResponse: 1:1 mirror of EntityCitationRecord.
# --------------------------------------------------------------------


def test_entity_citation_response_mirrors_record_fields() -> None:
    run_id = uuid4()
    record = _make_entity_citation(run_id=run_id)
    response = EntityCitationResponse.model_validate(record)
    assert response.id == record.id
    assert response.run_id == record.run_id
    assert response.entity_tenant_id == record.entity_tenant_id
    assert response.entity_name == record.entity_name
    assert response.entity_type == record.entity_type
    assert response.tenant_id == record.tenant_id
    assert response.source_chunk_ids == list(record.source_chunk_ids)


def test_entity_citation_response_source_chunk_ids_as_list() -> None:
    """Tuple-to-list serialisation per Pydantic v2 conventions."""
    run_id = uuid4()
    record = _make_entity_citation(run_id=run_id)
    response = EntityCitationResponse.model_validate(record)
    assert isinstance(response.source_chunk_ids, list)
    assert len(response.source_chunk_ids) == 2


def test_entity_citation_response_with_empty_source_chunk_ids() -> None:
    run_id = uuid4()
    record = EntityCitationRecord(
        id=uuid4(),
        run_id=run_id,
        entity_tenant_id=_TENANT_ID,
        entity_name="Orphan",
        entity_type="Organization",
        tenant_id=_TENANT_ID,
        source_chunk_ids=(),
    )
    response = EntityCitationResponse.model_validate(record)
    assert response.source_chunk_ids == []


# --------------------------------------------------------------------
# RunListResponse: envelope shape.
# --------------------------------------------------------------------


def test_run_list_response_with_runs_and_next_cursor() -> None:
    record_one = _make_run_record()
    record_two = _make_run_record()
    response = RunListResponse(
        runs=[
            RunResponse.model_validate(record_one),
            RunResponse.model_validate(record_two),
        ],
        next_cursor="opaque-base64-string",
    )
    assert len(response.runs) == 2
    assert response.next_cursor == "opaque-base64-string"


def test_run_list_response_with_empty_runs_and_no_cursor() -> None:
    response = RunListResponse(runs=[], next_cursor=None)
    assert response.runs == []
    assert response.next_cursor is None
    payload = json.loads(response.model_dump_json())
    assert payload == {"runs": [], "next_cursor": None}


def test_run_list_response_omits_citations_at_list_altitude() -> None:
    """Per D97, list-view runs carry empty citation tuples.

    The DTO does not enforce this (citations are optional fields with
    defaults); the adapter at PostgresRunHistoryReader.list_runs_with_filters
    is the enforcement point. Test verifies the DTO accepts empty lists
    cleanly for list-view responses.
    """
    record = _make_run_record(chunk_citations=(), entity_citations=())
    response = RunResponse.model_validate(record)
    list_response = RunListResponse(runs=[response], next_cursor=None)
    payload = json.loads(list_response.model_dump_json())
    assert payload["runs"][0]["chunk_citations"] == []
    assert payload["runs"][0]["entity_citations"] == []
