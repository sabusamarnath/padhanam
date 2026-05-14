"""Pydantic response DTOs for the run-history HTTP routes (D98, S34).

Field-for-field mirror of the run-history domain records. The HTTP
boundary preserves the storage-versus-render discipline from D96 by
declining to flatten, project, or rename fields. The Phase 2 UX
consumer renders citation excerpts, entity displays, and snapshot
fields at its altitude per D97's read-side commitment.

Pydantic v2 conventions:

- ``model_config = ConfigDict(from_attributes=True)`` so domain
  records pass through ``RunResponse.model_validate(run_record)``
  cleanly without manual field mapping.
- Tuple types on the domain records (``chunk_citations``,
  ``entity_citations``, ``source_chunk_ids``) surface as
  ``list[...]`` per Pydantic v2's default tuple-to-list JSON
  serialisation.
- ``source_snapshot`` JSONB surfaces as ``dict[str, Any]``
  (intentionally schemaless per D96 to accommodate ingestion
  enrichment evolution).
- ``Decimal`` cost serialises as string per the project's monetary
  serialisation convention.
- ``UUID`` and ``datetime`` use Pydantic v2 defaults (canonical hex
  for UUID, ISO 8601 for datetime).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChunkCitationResponse(BaseModel):
    """Mirrors ``ChunkCitationRecord`` 1:1 per D98."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    chunk_id: UUID | None
    tenant_id: str
    jurisdiction: str
    chunk_excerpt: str
    source_snapshot: dict[str, Any] = Field(default_factory=dict)


class EntityCitationResponse(BaseModel):
    """Mirrors ``EntityCitationRecord`` 1:1 per D98."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    entity_tenant_id: str
    entity_name: str
    entity_type: str
    tenant_id: str
    source_chunk_ids: list[UUID]


class RunResponse(BaseModel):
    """Mirrors ``RunRecord`` 1:1 per D98.

    Citation tuples on the domain record surface as lists per
    Pydantic v2's default tuple-to-list serialisation. The list-view
    altitude returns instances with empty citation lists per D97;
    the detail-view altitude returns instances with citations
    populated from the joined queries.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: str
    jurisdiction: str
    agent_template_id: UUID
    agent_template_version: int
    input_message: str
    output_content: str
    started_at: datetime
    completed_at: datetime
    termination_reason: str
    iteration_count: int
    total_cost_usd: Decimal
    trace_id: str | None
    audit_start_hash: str
    audit_end_hash: str | None
    created_at: datetime
    chunk_citations: list[ChunkCitationResponse] = Field(default_factory=list)
    entity_citations: list[EntityCitationResponse] = Field(default_factory=list)


class RunListResponse(BaseModel):
    """Envelope for ``GET /runs`` per D98.

    Carries the page of runs (each with empty citation lists per
    D97's bounded-cardinality argument at list-view altitude) plus
    the opaque next-cursor string when more pages exist. The cursor
    is the base64-of-JSON opaque shape from
    ``contexts.run_history.application.cursor``; the consumer treats
    it as a black box and passes it back verbatim.
    """

    runs: list[RunResponse]
    next_cursor: str | None = None


__all__ = [
    "ChunkCitationResponse",
    "EntityCitationResponse",
    "RunListResponse",
    "RunResponse",
]
