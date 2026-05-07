"""extract_source — extraction-stage worker use case (D64).

The worker calls ``extract_source`` once per claimed source. The
use case orchestrates:

  1. Load the source's chunks via the SourceRepositoryPort. The
     chunks already carry text + structural metadata + embedding
     (the parse and embed stages wrote them); the extract stage
     reads the text and produces graph rows.

  2. Hand the chunks to the EntityExtractorPort. The port returns
     an ExtractionResult carrying entities and relationships
     surfaced from the chunks. ``source_chunk_ids`` on each Entity
     and ``source_chunk_id`` on each Relationship preserve
     provenance.

  3. Write entities first, then relationships, through the
     GraphRepositoryPort. Order matters: the relationship MERGE
     pattern MATCHes endpoint entities by their composite key, so
     entities must exist before the relationship MERGEs run. Both
     writes are idempotent on Neo4j MERGE so re-running the stage
     against the same chunks produces no duplicate nodes or edges.

  4. Transition source state to INDEXED on success or
     EXTRACTION_FAILED on ExtractorError /
     ExtractorConfigurationError / GraphRepositoryError /
     GraphRepositoryConfigurationError with extraction_error_text
     populated. ``indexed`` is the terminal-success state for P6
     close.

The caller is responsible for having already claimed the source
(transitioned it to EXTRACTING via ``claim_pending_for_extract``).
extract_source completes the state transition: INDEXED on success,
EXTRACTION_FAILED on extractor or graph-repository exception.

The empty-chunks case (an embedded source with no chunks — would
be a parse stage anomaly but defensively handled here) transitions
straight to INDEXED with no extractor or repository call. The
worker logs the zero-chunk case for operator visibility.

Returns ``ExtractResult`` so callers (the worker loop, tests) can
observe whether the extract succeeded plus how many entities and
relationships landed; the operator-visible signal is the
source.state transition, this is for telemetry / test assertions.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from contexts.ingestion.domain.source import Source
from contexts.ingestion.domain.state import SourceState
from contexts.ingestion.ports.entity_extractor_port import (
    EntityExtractorPort,
    ExtractorConfigurationError,
    ExtractorError,
)
from contexts.ingestion.ports.graph_repository_port import (
    GraphRepositoryConfigurationError,
    GraphRepositoryError,
    GraphRepositoryPort,
)
from contexts.ingestion.ports.source_repository_port import (
    SourceRepositoryPort,
)
from shared_kernel import TenantContext


@dataclass(frozen=True)
class ExtractResult:
    source_id: UUID
    final_state: SourceState
    entities_written: int
    relationships_written: int
    extraction_error_text: str | None


async def extract_source(
    *,
    source: Source,
    repository: SourceRepositoryPort,
    extractor: EntityExtractorPort,
    graph_repository: GraphRepositoryPort,
    tenant_context: TenantContext,
) -> ExtractResult:
    """Extract a single claimed source's chunks and write entities
    plus relationships into Neo4j.

    Catches all four port-level error types as the
    extraction_failed path; the distinction between retryable and
    non-retryable matters for future retry policy but at S21 they
    land identically in the source state.
    """
    chunks = await repository.get_chunks_for_source(
        source_id=source.id, tenant_id=source.tenant_id
    )
    if not chunks:
        await repository.update_source_state(
            source_id=source.id,
            tenant_id=source.tenant_id,
            new_state=SourceState.INDEXED,
        )
        return ExtractResult(
            source_id=source.id,
            final_state=SourceState.INDEXED,
            entities_written=0,
            relationships_written=0,
            extraction_error_text=None,
        )

    try:
        result = await extractor.extract(chunks, tenant_context)
    except (ExtractorError, ExtractorConfigurationError) as exc:
        await repository.update_source_state(
            source_id=source.id,
            tenant_id=source.tenant_id,
            new_state=SourceState.EXTRACTION_FAILED,
            extraction_error_text=str(exc),
        )
        return ExtractResult(
            source_id=source.id,
            final_state=SourceState.EXTRACTION_FAILED,
            entities_written=0,
            relationships_written=0,
            extraction_error_text=str(exc),
        )

    try:
        await graph_repository.merge_entities(
            entities=result.entities, tenant_context=tenant_context
        )
        await graph_repository.merge_relationships(
            relationships=result.relationships, tenant_context=tenant_context
        )
    except (
        GraphRepositoryError,
        GraphRepositoryConfigurationError,
    ) as exc:
        await repository.update_source_state(
            source_id=source.id,
            tenant_id=source.tenant_id,
            new_state=SourceState.EXTRACTION_FAILED,
            extraction_error_text=str(exc),
        )
        return ExtractResult(
            source_id=source.id,
            final_state=SourceState.EXTRACTION_FAILED,
            entities_written=0,
            relationships_written=0,
            extraction_error_text=str(exc),
        )

    await repository.update_source_state(
        source_id=source.id,
        tenant_id=source.tenant_id,
        new_state=SourceState.INDEXED,
    )
    return ExtractResult(
        source_id=source.id,
        final_state=SourceState.INDEXED,
        entities_written=len(result.entities),
        relationships_written=len(result.relationships),
        extraction_error_text=None,
    )
