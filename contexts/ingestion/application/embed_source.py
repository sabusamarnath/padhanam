"""embed_source — embedding-stage worker use case (D62).

The worker calls ``embed_source`` once per claimed source. The use
case orchestrates:

  1. Load the source's chunks via the repository port. The chunks
     already exist (the parse stage wrote them); the embed stage
     adds vectors to them.

  2. Hand the chunks to the ChunkEmbedder port. The port returns
     one Embedding per Chunk in input order, each carrying the
     source chunk_id so the write path doesn't depend on positional
     alignment.

  3. UPSERT embeddings via the repository per D62. Idempotent re-
     embed: re-running the stage replaces the vector for each
     chunk_id rather than producing a duplicate row (the embedding
     lives on the chunks row itself; UPSERT collapses to UPDATE).

  4. Transition source state to EMBEDDED on success or
     EMBEDDING_FAILED on EmbedderError / EmbedderConfigurationError
     with embedding_error_text populated. The transitions mirror the
     parse stage's PARSED/FAILED shape.

The caller is responsible for having already claimed the source
(transitioned it to EMBEDDING via claim_pending_for_embed). embed_
source completes the state transition: EMBEDDED on success,
EMBEDDING_FAILED on embedder exception.

The empty-chunks case (a parsed source with no chunks — would be
a parse stage anomaly but defensively handled here) transitions
straight to EMBEDDED with no embedder call. The worker logs the
zero-chunk case for operator visibility.

Returns ``EmbedResult`` so callers (the worker loop, tests) can
observe whether the embed succeeded plus how many embeddings
landed; the operator-visible signal is the source.state transition,
this is for telemetry / test assertions.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from contexts.ingestion.domain.embedding_task import EmbeddingTask
from contexts.ingestion.domain.source import Source
from contexts.ingestion.domain.state import SourceState
from contexts.ingestion.ports.chunk_embedder_port import (
    ChunkEmbedderPort,
    EmbedderConfigurationError,
    EmbedderError,
)
from contexts.ingestion.ports.source_repository_port import (
    SourceRepositoryPort,
)
from shared_kernel import TenantContext


@dataclass(frozen=True)
class EmbedResult:
    source_id: UUID
    final_state: SourceState
    embeddings_written: int
    embedding_error_text: str | None


async def embed_source(
    *,
    source: Source,
    repository: SourceRepositoryPort,
    embedder: ChunkEmbedderPort,
    tenant_context: TenantContext,
) -> EmbedResult:
    """Embed a single claimed source's chunks and write the vectors.

    Catches EmbedderError and EmbedderConfigurationError both as the
    embedding_failed path; the distinction between retryable and
    non-retryable matters for future retry policy but at S20 they
    land identically in the source state.
    """
    chunks = await repository.get_chunks_for_source(
        source_id=source.id, tenant_id=source.tenant_id
    )
    if not chunks:
        # Parsed source with no chunks — unusual but cleanly handled
        # by transitioning straight to EMBEDDED. The operator-
        # visible signal is the zero embeddings_written count in
        # the worker log.
        await repository.update_source_state(
            source_id=source.id,
            tenant_id=source.tenant_id,
            new_state=SourceState.EMBEDDED,
        )
        return EmbedResult(
            source_id=source.id,
            final_state=SourceState.EMBEDDED,
            embeddings_written=0,
            embedding_error_text=None,
        )

    try:
        # D65: ingestion-time embedding always passes DOCUMENT so the
        # nomic-embed-text v1.5 ``search_document:`` prefix lands at
        # the corpus side. Retrieval-side embedding (S22 vector
        # adapter) passes QUERY for the corresponding query prefix.
        embeddings = await embedder.embed(
            chunks, tenant_context, EmbeddingTask.DOCUMENT
        )
    except (EmbedderError, EmbedderConfigurationError) as exc:
        await repository.update_source_state(
            source_id=source.id,
            tenant_id=source.tenant_id,
            new_state=SourceState.EMBEDDING_FAILED,
            embedding_error_text=str(exc),
        )
        return EmbedResult(
            source_id=source.id,
            final_state=SourceState.EMBEDDING_FAILED,
            embeddings_written=0,
            embedding_error_text=str(exc),
        )

    await repository.upsert_chunk_embeddings(
        embeddings=embeddings, tenant_id=source.tenant_id
    )
    await repository.update_source_state(
        source_id=source.id,
        tenant_id=source.tenant_id,
        new_state=SourceState.EMBEDDED,
    )
    return EmbedResult(
        source_id=source.id,
        final_state=SourceState.EMBEDDED,
        embeddings_written=len(embeddings),
        embedding_error_text=None,
    )
