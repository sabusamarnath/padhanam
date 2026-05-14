"""Pydantic response DTOs for the ingestion management HTTP routes (D104, S38).

Field-for-field mirror of the ingestion-context source aggregate
plus the projected status surface. The HTTP boundary preserves the
storage-versus-render discipline established at D96 by declining
to flatten or rename fields beyond the projection needed to keep
``raw_content`` off the wire (bytes columns do not belong in HTTP
response bodies; the file payload is server-side concern only).

Pydantic v2 conventions mirror the run-history and audit precedents
at ``_run_history_dto.py`` and ``_audit_dto.py``:

- ``model_config = ConfigDict(from_attributes=True)`` so domain
  records pass through ``SourceDTO.model_validate(record)`` cleanly
  without manual field mapping.
- ``UUID`` and ``datetime`` use Pydantic v2 defaults (canonical hex
  for UUID, ISO 8601 for datetime).
- ``next_cursor`` on the page envelope is the opaque base64-of-JSON
  string from ``contexts.ingestion.application.cursor``; the route
  handler encodes the domain ``SourceListCursor`` before constructing
  the DTO. Consumers treat it as a black box.
- ``SourceStatusDTO`` is a thin projection of ``Source`` per Path A
  from S38 reconciliation: the get-status route reuses the existing
  ``get_source`` use case and emits a status-focused DTO rather than
  introducing a separate ``get_source_status`` application use case.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from contexts.ingestion.domain.source import Source


class SourceDTO(BaseModel):
    """Mirrors ``Source`` 1:1 minus ``raw_content`` per D104.

    ``raw_content`` bytes stay off the wire — the ingestion management
    API at S38 exposes source metadata and status only; file payloads
    are server-side concern reachable via worker-side IO paths.

    The three error-text fields surface verbatim so operators
    inspecting a failed source can see the captured failure reason
    without an extra round-trip to the status endpoint.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: str
    jurisdiction: str
    file_name: str
    file_type: str
    file_size_bytes: int
    state: str
    parsing_error_text: str | None = None
    embedding_error_text: str | None = None
    extraction_error_text: str | None = None
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime


def source_to_dto(source: Source) -> SourceDTO:
    """Convert a ``Source`` aggregate to its HTTP DTO.

    Pydantic's ``from_attributes=True`` handles all fields except
    ``state``: the domain layer uses ``SourceState`` (StrEnum); the
    DTO surfaces the raw string value so consumers see the enum's
    wire form rather than the Python class name.
    """
    return SourceDTO(
        id=source.id,
        tenant_id=source.tenant_id,
        jurisdiction=source.jurisdiction,
        file_name=source.file_name,
        file_type=source.file_type,
        file_size_bytes=source.file_size_bytes,
        state=source.state.value,
        parsing_error_text=source.parsing_error_text,
        embedding_error_text=source.embedding_error_text,
        extraction_error_text=source.extraction_error_text,
        created_by_user_id=source.created_by_user_id,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


class SourceListPageDTO(BaseModel):
    """Envelope for ``GET /ingestion/sources`` per D104.

    Carries the page of sources and the optional next-cursor string
    (opaque base64-of-JSON shape from
    ``contexts.ingestion.application.cursor``). Consumers treat
    ``next_cursor`` as a black box and pass it back verbatim on the
    next request.
    """

    model_config = ConfigDict(from_attributes=True)

    sources: list[SourceDTO]
    next_cursor: str | None = None


class SourceStatusDTO(BaseModel):
    """Projection of ``Source`` carrying the pipeline status surface (D104).

    ``GET /ingestion/sources/{source_id}/status`` returns this thin
    DTO. The HTTP route calls the existing ``get_source`` use case
    and projects the state-relevant fields rather than introducing a
    separate ``get_source_status`` use case (Path A from S38
    reconciliation: derive status from the Source aggregate rather
    than stand up new application surface).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    state: str
    parsing_error_text: str | None = None
    embedding_error_text: str | None = None
    extraction_error_text: str | None = None
    updated_at: datetime


def source_to_status_dto(source: Source) -> SourceStatusDTO:
    """Project a ``Source`` aggregate to the status DTO."""
    return SourceStatusDTO(
        id=source.id,
        state=source.state.value,
        parsing_error_text=source.parsing_error_text,
        embedding_error_text=source.embedding_error_text,
        extraction_error_text=source.extraction_error_text,
        updated_at=source.updated_at,
    )


__all__ = [
    "SourceDTO",
    "SourceListPageDTO",
    "SourceStatusDTO",
    "source_to_dto",
    "source_to_status_dto",
]
