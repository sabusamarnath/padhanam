"""Unit tests for the ingestion management HTTP DTOs (D104, S38).

Cover field-for-field conversion from Source aggregate to SourceDTO,
the SourceListPageDTO envelope, and the SourceStatusDTO projection.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from apps.api.routers._ingestion_dto import (
    SourceDTO,
    SourceListPageDTO,
    SourceStatusDTO,
    source_to_dto,
    source_to_status_dto,
)
from contexts.ingestion.domain.source import Source
from contexts.ingestion.domain.state import SourceState


def _make_source(
    *,
    state: SourceState = SourceState.INDEXED,
    parsing_error_text: str | None = None,
    embedding_error_text: str | None = None,
    extraction_error_text: str | None = None,
) -> Source:
    now = datetime(2026, 5, 14, 10, 30, tzinfo=timezone.utc)
    return Source(
        id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        tenant_id="tenant-a",
        jurisdiction="UK",
        file_name="example.md",
        file_type="md",
        file_size_bytes=42,
        raw_content=b"# example content",
        state=state,
        parsing_error_text=parsing_error_text,
        created_by_user_id="user-1",
        created_at=now,
        updated_at=now,
        embedding_error_text=embedding_error_text,
        extraction_error_text=extraction_error_text,
    )


# --------------------------------------------------------------------
# SourceDTO conversion.
# --------------------------------------------------------------------


def test_source_to_dto_carries_all_metadata_fields() -> None:
    source = _make_source()
    dto = source_to_dto(source)

    assert dto.id == source.id
    assert dto.tenant_id == "tenant-a"
    assert dto.jurisdiction == "UK"
    assert dto.file_name == "example.md"
    assert dto.file_type == "md"
    assert dto.file_size_bytes == 42
    assert dto.state == "indexed"
    assert dto.parsing_error_text is None
    assert dto.embedding_error_text is None
    assert dto.extraction_error_text is None
    assert dto.created_by_user_id == "user-1"
    assert dto.created_at == source.created_at
    assert dto.updated_at == source.updated_at


def test_source_to_dto_does_not_expose_raw_content() -> None:
    source = _make_source()
    dto = source_to_dto(source)
    assert "raw_content" not in dto.model_dump()


def test_source_to_dto_state_uses_string_value() -> None:
    """The state field surfaces as the string value (not the StrEnum class
    name) so consumers see the wire form."""
    source = _make_source(state=SourceState.EMBEDDING_FAILED)
    dto = source_to_dto(source)
    assert dto.state == "embedding_failed"


def test_source_to_dto_carries_error_texts_when_present() -> None:
    source = _make_source(
        state=SourceState.EXTRACTION_FAILED,
        parsing_error_text="parse problem",
        embedding_error_text="embed problem",
        extraction_error_text="extract problem",
    )
    dto = source_to_dto(source)
    assert dto.parsing_error_text == "parse problem"
    assert dto.embedding_error_text == "embed problem"
    assert dto.extraction_error_text == "extract problem"


# --------------------------------------------------------------------
# SourceListPageDTO envelope.
# --------------------------------------------------------------------


def test_source_list_page_dto_carries_sources_and_optional_cursor() -> None:
    sources = [source_to_dto(_make_source())]
    page = SourceListPageDTO(sources=sources, next_cursor="abc123")
    assert page.sources == sources
    assert page.next_cursor == "abc123"


def test_source_list_page_dto_empty_with_no_cursor() -> None:
    page = SourceListPageDTO(sources=[], next_cursor=None)
    assert page.sources == []
    assert page.next_cursor is None


# --------------------------------------------------------------------
# SourceStatusDTO projection.
# --------------------------------------------------------------------


def test_source_to_status_dto_projects_status_fields_only() -> None:
    source = _make_source(state=SourceState.EMBEDDED)
    status = source_to_status_dto(source)
    assert status.id == source.id
    assert status.state == "embedded"
    assert status.parsing_error_text is None
    assert status.embedding_error_text is None
    assert status.extraction_error_text is None
    assert status.updated_at == source.updated_at


def test_source_to_status_dto_excludes_metadata_fields() -> None:
    source = _make_source()
    status_dump = source_to_status_dto(source).model_dump()
    for excluded_field in (
        "tenant_id",
        "jurisdiction",
        "file_name",
        "file_type",
        "file_size_bytes",
        "created_by_user_id",
        "created_at",
        "raw_content",
    ):
        assert excluded_field not in status_dump


def test_source_to_status_dto_surfaces_failure_text() -> None:
    source = _make_source(
        state=SourceState.FAILED,
        parsing_error_text="parser hit invalid markdown frontmatter",
    )
    status = source_to_status_dto(source)
    assert status.state == "failed"
    assert status.parsing_error_text == "parser hit invalid markdown frontmatter"
