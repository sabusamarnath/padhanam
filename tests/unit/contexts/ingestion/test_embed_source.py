"""Unit tests for the embed_source application use case (S20 / D62).

Domain-shape assertions: the use case orchestrates load → embed →
upsert → state-transition with the right ports and the right
EmbedResult shape on success and on failure.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID, uuid4

import pytest

from contexts.ingestion.application.embed_source import (
    EmbedResult,
    embed_source,
)
from contexts.ingestion.domain.chunk import Chunk
from contexts.ingestion.domain.embedding import Embedding
from contexts.ingestion.domain.source import Source
from contexts.ingestion.domain.state import SourceState
from contexts.ingestion.ports.chunk_embedder_port import (
    EmbedderConfigurationError,
    EmbedderError,
)
from shared_kernel import TenantContext


_TENANT_A = TenantContext(
    tenant_id="tenant-a",
    jurisdiction="eu-west",
    cost_attribution_id="tenant-a",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _source(state: SourceState = SourceState.EMBEDDING) -> Source:
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


def _chunk(source_id: UUID, idx: int, content: str = "x") -> Chunk:
    return Chunk(
        id=uuid4(),
        source_id=source_id,
        tenant_id="tenant-a",
        jurisdiction="eu-west",
        chunk_index=idx,
        content=content,
    )


class _FakeRepository:
    def __init__(self, chunks_for_source: Sequence[Chunk]) -> None:
        self._chunks = list(chunks_for_source)
        self.upserted: list[Embedding] = []
        self.state_transitions: list[
            tuple[UUID, SourceState, str | None, str | None]
        ] = []

    async def get_chunks_for_source(
        self, source_id: UUID, tenant_id: str
    ) -> Sequence[Chunk]:
        return [c for c in self._chunks if c.source_id == source_id]

    async def upsert_chunk_embeddings(
        self, embeddings: Sequence[Embedding], tenant_id: str
    ) -> None:
        self.upserted.extend(embeddings)

    async def update_source_state(
        self,
        source_id: UUID,
        tenant_id: str,
        new_state: SourceState,
        parsing_error_text: str | None = None,
        embedding_error_text: str | None = None,
    ) -> None:
        self.state_transitions.append(
            (source_id, new_state, parsing_error_text, embedding_error_text)
        )


class _FakeEmbedder:
    def __init__(self, vectors_per_chunk: list[list[float]]) -> None:
        self._vectors = vectors_per_chunk
        self.calls: list[tuple[Sequence[Chunk], TenantContext]] = []

    async def embed(
        self, chunks: Sequence[Chunk], tenant_context: TenantContext
    ) -> Sequence[Embedding]:
        self.calls.append((chunks, tenant_context))
        return [
            Embedding(
                chunk_id=chunks[i].id,
                vector=self._vectors[i],
                model="nomic-embed-text:v1.5",
            )
            for i in range(len(chunks))
        ]


class _RaisingEmbedder:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def embed(
        self, chunks: Sequence[Chunk], tenant_context: TenantContext
    ) -> Sequence[Embedding]:
        raise self._exc


def test_embed_source_success_writes_embeddings_and_transitions_to_embedded() -> None:
    source = _source()
    chunks = [_chunk(source.id, 0), _chunk(source.id, 1)]
    repository = _FakeRepository(chunks)
    embedder = _FakeEmbedder([[0.1] * 768, [0.2] * 768])

    result = asyncio.run(
        embed_source(
            source=source,
            repository=repository,
            embedder=embedder,
            tenant_context=_TENANT_A,
        )
    )

    assert isinstance(result, EmbedResult)
    assert result.final_state == SourceState.EMBEDDED
    assert result.embeddings_written == 2
    assert result.embedding_error_text is None
    assert len(repository.upserted) == 2
    assert {e.chunk_id for e in repository.upserted} == {c.id for c in chunks}
    # Last state transition is to EMBEDDED with no error text.
    assert repository.state_transitions[-1] == (
        source.id,
        SourceState.EMBEDDED,
        None,
        None,
    )


def test_embed_source_calls_embedder_with_loaded_chunks_and_tenant_context() -> None:
    source = _source()
    chunks = [_chunk(source.id, 0)]
    repository = _FakeRepository(chunks)
    embedder = _FakeEmbedder([[0.1] * 768])

    asyncio.run(
        embed_source(
            source=source,
            repository=repository,
            embedder=embedder,
            tenant_context=_TENANT_A,
        )
    )

    assert len(embedder.calls) == 1
    called_chunks, called_ctx = embedder.calls[0]
    assert list(called_chunks) == chunks
    assert called_ctx == _TENANT_A


def test_embed_source_zero_chunks_transitions_to_embedded_without_calling_embedder() -> None:
    """A parsed source with no chunks is unusual but defensively
    handled — the use case transitions straight to EMBEDDED with
    embeddings_written=0 and no embedder call."""
    source = _source()
    repository = _FakeRepository([])  # no chunks for this source
    embedder = _FakeEmbedder([])

    result = asyncio.run(
        embed_source(
            source=source,
            repository=repository,
            embedder=embedder,
            tenant_context=_TENANT_A,
        )
    )

    assert result.final_state == SourceState.EMBEDDED
    assert result.embeddings_written == 0
    assert repository.upserted == []
    assert len(repository.state_transitions) == 1


def test_embedder_error_transitions_to_embedding_failed_with_error_text() -> None:
    source = _source()
    chunks = [_chunk(source.id, 0)]
    repository = _FakeRepository(chunks)
    embedder = _RaisingEmbedder(EmbedderError("gateway connection refused"))

    result = asyncio.run(
        embed_source(
            source=source,
            repository=repository,
            embedder=embedder,
            tenant_context=_TENANT_A,
        )
    )

    assert result.final_state == SourceState.EMBEDDING_FAILED
    assert result.embeddings_written == 0
    assert result.embedding_error_text == "gateway connection refused"
    assert repository.upserted == []
    # Last state transition carries the embedding_error_text.
    src_id, state, parsing_err, embed_err = repository.state_transitions[-1]
    assert src_id == source.id
    assert state == SourceState.EMBEDDING_FAILED
    assert parsing_err is None
    assert embed_err == "gateway connection refused"


def test_embedder_configuration_error_also_transitions_to_embedding_failed() -> None:
    """Per D62: at S20 EmbedderError and EmbedderConfigurationError
    land identically in source state. The retry-policy distinction
    matters at a future cost-attribution session, not at S20."""
    source = _source()
    chunks = [_chunk(source.id, 0)]
    repository = _FakeRepository(chunks)
    embedder = _RaisingEmbedder(
        EmbedderConfigurationError("bad master key")
    )

    result = asyncio.run(
        embed_source(
            source=source,
            repository=repository,
            embedder=embedder,
            tenant_context=_TENANT_A,
        )
    )

    assert result.final_state == SourceState.EMBEDDING_FAILED
    assert result.embedding_error_text == "bad master key"
