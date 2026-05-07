"""Unit tests for the extract_source application use case (S21 / D64).

Domain-shape assertions: the use case orchestrates load chunks →
extract → merge entities → merge relationships → state-transition
with the right ports and the right ExtractResult shape on the
success path and each of the four failure paths (extractor
retryable, extractor configuration, graph retryable, graph
configuration).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID, uuid4

from contexts.ingestion.application.extract_source import (
    ExtractResult,
    extract_source,
)
from contexts.ingestion.domain.chunk import Chunk
from contexts.ingestion.domain.entity import Entity
from contexts.ingestion.domain.extraction_result import ExtractionResult
from contexts.ingestion.domain.relationship import EntityRef, Relationship
from contexts.ingestion.domain.source import Source
from contexts.ingestion.domain.state import SourceState
from contexts.ingestion.ports.entity_extractor_port import (
    ExtractorConfigurationError,
    ExtractorError,
)
from contexts.ingestion.ports.graph_repository_port import (
    GraphRepositoryConfigurationError,
    GraphRepositoryError,
)
from shared_kernel import TenantContext


_TENANT_A = TenantContext(
    tenant_id="tenant-a",
    jurisdiction="eu-west",
    cost_attribution_id="tenant-a",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _source(state: SourceState = SourceState.EXTRACTING) -> Source:
    return Source(
        id=uuid4(),
        tenant_id="tenant-a",
        jurisdiction="eu-west",
        file_name="x.md",
        file_type="markdown",
        file_size_bytes=10,
        raw_content=b"# hi\n",
        state=state,
        parsing_error_text=None,
        created_by_user_id="user-1",
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )


def _chunk(source_id: UUID, idx: int) -> Chunk:
    return Chunk(
        id=uuid4(),
        source_id=source_id,
        tenant_id="tenant-a",
        jurisdiction="eu-west",
        chunk_index=idx,
        content=f"chunk content {idx}",
    )


class _FakeRepository:
    def __init__(self, chunks: Sequence[Chunk]) -> None:
        self._chunks = chunks
        self.state_calls: list[tuple[SourceState, str | None]] = []

    async def get_chunks_for_source(self, *, source_id: UUID, tenant_id: str) -> Sequence[Chunk]:  # noqa: D401
        return self._chunks

    async def update_source_state(
        self,
        *,
        source_id: UUID,
        tenant_id: str,
        new_state: SourceState,
        parsing_error_text: str | None = None,
        embedding_error_text: str | None = None,
        extraction_error_text: str | None = None,
    ) -> None:
        self.state_calls.append((new_state, extraction_error_text))


class _FakeExtractor:
    def __init__(self, result: ExtractionResult | Exception) -> None:
        self._result = result
        self.calls: list[tuple[Sequence[Chunk], TenantContext]] = []

    async def extract(
        self,
        chunks: Sequence[Chunk],
        tenant_context: TenantContext,
    ) -> ExtractionResult:
        self.calls.append((tuple(chunks), tenant_context))
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class _FakeGraphRepository:
    def __init__(self, raise_on_entities: Exception | None = None,
                 raise_on_relationships: Exception | None = None) -> None:
        self._raise_on_entities = raise_on_entities
        self._raise_on_relationships = raise_on_relationships
        self.merged_entities: list[Sequence[Entity]] = []
        self.merged_relationships: list[Sequence[Relationship]] = []

    async def merge_entities(
        self, entities: Sequence[Entity], tenant_context: TenantContext
    ) -> None:
        if self._raise_on_entities is not None:
            raise self._raise_on_entities
        self.merged_entities.append(tuple(entities))

    async def merge_relationships(
        self,
        relationships: Sequence[Relationship],
        tenant_context: TenantContext,
    ) -> None:
        if self._raise_on_relationships is not None:
            raise self._raise_on_relationships
        self.merged_relationships.append(tuple(relationships))


def _entity(name: str = "ACME") -> Entity:
    return Entity(
        tenant_id="tenant-a",
        jurisdiction="eu-west",
        name=name,
        entity_type="Organisation",
    )


def _relationship() -> Relationship:
    return Relationship(
        tenant_id="tenant-a",
        jurisdiction="eu-west",
        source=EntityRef(name="ACME", entity_type="Organisation"),
        target=EntityRef(name="Alice", entity_type="Person"),
        relationship_type="employs",
        source_chunk_id=uuid4(),
    )


def test_extract_source_indexed_on_success() -> None:
    src = _source()
    chunks = [_chunk(src.id, 0)]
    extraction = ExtractionResult(
        entities=(_entity(),),
        relationships=(_relationship(),),
    )
    repo = _FakeRepository(chunks)
    extractor = _FakeExtractor(extraction)
    graph = _FakeGraphRepository()

    async def run() -> ExtractResult:
        return await extract_source(
            source=src,
            repository=repo,
            extractor=extractor,
            graph_repository=graph,
            tenant_context=_TENANT_A,
        )

    result = asyncio.run(run())

    assert result.final_state == SourceState.INDEXED
    assert result.entities_written == 1
    assert result.relationships_written == 1
    assert result.extraction_error_text is None
    assert repo.state_calls == [(SourceState.INDEXED, None)]
    assert len(graph.merged_entities) == 1
    assert len(graph.merged_relationships) == 1


def test_extract_source_empty_chunks_transitions_to_indexed() -> None:
    src = _source()
    repo = _FakeRepository([])
    extractor = _FakeExtractor(ExtractionResult())
    graph = _FakeGraphRepository()

    async def run() -> ExtractResult:
        return await extract_source(
            source=src,
            repository=repo,
            extractor=extractor,
            graph_repository=graph,
            tenant_context=_TENANT_A,
        )

    result = asyncio.run(run())

    assert result.final_state == SourceState.INDEXED
    assert result.entities_written == 0
    assert result.relationships_written == 0
    assert repo.state_calls == [(SourceState.INDEXED, None)]
    # Empty chunks: extractor and graph repo not invoked.
    assert extractor.calls == []
    assert graph.merged_entities == []


def test_extract_source_extractor_error_to_extraction_failed() -> None:
    src = _source()
    chunks = [_chunk(src.id, 0)]
    repo = _FakeRepository(chunks)
    extractor = _FakeExtractor(ExtractorError("gateway down"))
    graph = _FakeGraphRepository()

    async def run() -> ExtractResult:
        return await extract_source(
            source=src,
            repository=repo,
            extractor=extractor,
            graph_repository=graph,
            tenant_context=_TENANT_A,
        )

    result = asyncio.run(run())

    assert result.final_state == SourceState.EXTRACTION_FAILED
    assert result.entities_written == 0
    assert "gateway down" in (result.extraction_error_text or "")
    assert repo.state_calls == [
        (SourceState.EXTRACTION_FAILED, "gateway down")
    ]
    assert graph.merged_entities == []


def test_extract_source_extractor_configuration_error_to_extraction_failed() -> None:
    src = _source()
    chunks = [_chunk(src.id, 0)]
    repo = _FakeRepository(chunks)
    extractor = _FakeExtractor(ExtractorConfigurationError("bad json"))
    graph = _FakeGraphRepository()

    async def run() -> ExtractResult:
        return await extract_source(
            source=src,
            repository=repo,
            extractor=extractor,
            graph_repository=graph,
            tenant_context=_TENANT_A,
        )

    result = asyncio.run(run())

    assert result.final_state == SourceState.EXTRACTION_FAILED
    assert "bad json" in (result.extraction_error_text or "")


def test_extract_source_graph_error_to_extraction_failed() -> None:
    src = _source()
    chunks = [_chunk(src.id, 0)]
    extraction = ExtractionResult(entities=(_entity(),), relationships=())
    repo = _FakeRepository(chunks)
    extractor = _FakeExtractor(extraction)
    graph = _FakeGraphRepository(
        raise_on_entities=GraphRepositoryError("neo4j unavailable")
    )

    async def run() -> ExtractResult:
        return await extract_source(
            source=src,
            repository=repo,
            extractor=extractor,
            graph_repository=graph,
            tenant_context=_TENANT_A,
        )

    result = asyncio.run(run())

    assert result.final_state == SourceState.EXTRACTION_FAILED
    assert "neo4j unavailable" in (result.extraction_error_text or "")


def test_extract_source_graph_relationship_error_to_extraction_failed() -> None:
    """Failure during relationship MERGE after entity MERGE succeeded
    still lands in extraction_failed; the partial success is fine
    because re-running the stage MERGE-deduplicates the entities."""
    src = _source()
    chunks = [_chunk(src.id, 0)]
    extraction = ExtractionResult(
        entities=(_entity(),), relationships=(_relationship(),)
    )
    repo = _FakeRepository(chunks)
    extractor = _FakeExtractor(extraction)
    graph = _FakeGraphRepository(
        raise_on_relationships=GraphRepositoryConfigurationError(
            "schema mismatch"
        )
    )

    async def run() -> ExtractResult:
        return await extract_source(
            source=src,
            repository=repo,
            extractor=extractor,
            graph_repository=graph,
            tenant_context=_TENANT_A,
        )

    result = asyncio.run(run())

    assert result.final_state == SourceState.EXTRACTION_FAILED
    assert "schema mismatch" in (result.extraction_error_text or "")
    # Entity MERGE landed before the relationship failure — that's
    # idempotent on re-run, so we don't roll it back.
    assert len(graph.merged_entities) == 1
