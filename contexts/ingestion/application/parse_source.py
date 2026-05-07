"""parse_source — worker-side use case (D60 / D61).

The worker calls ``parse_source`` once per claimed source. The use
case orchestrates:

  1. Parse the source's raw_content via the parser port for the
     source's file_type. ParserError signals structurally-invalid
     content (the worker marks the source FAILED with the error
     text in parsing_error_text).
  2. Build Chunk rows from the ParsedContent (one Chunk per
     ParsedChunk; chunk_index assigned positionally).
  3. Write chunks atomically with the state transition to PARSED.
     Both adapter calls happen sequentially within the worker's
     transactional discipline (the adapter handles its own commits
     per call; the worker treats the chunk-save-then-state-update
     sequence as the atomic unit at the application level — the
     UNIQUE(source_id, chunk_index) backstop per D60 fences a
     mid-flow crash from leaving duplicate rows on retry).

The use case is async because the repository and the registry are
async; the parser itself is synchronous CPU work and runs on the
event loop's thread (markdown-it-py's parse is in-process and
fast for the source sizes Phase 1 expects).

Returns a small dataclass ParseResult so callers (the worker
loop, tests) can observe whether the parse succeeded plus how many
chunks landed; the operator-visible signal is the source.state
transition itself, this is for telemetry / test assertions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from uuid import UUID, uuid4

from contexts.ingestion.domain.chunk import Chunk
from contexts.ingestion.domain.source import Source
from contexts.ingestion.domain.state import SourceState
from contexts.ingestion.ports.parser_port import ParserError, ParserPort
from contexts.ingestion.ports.source_repository_port import SourceRepositoryPort


@dataclass(frozen=True)
class ParseResult:
    source_id: UUID
    final_state: SourceState
    chunks_written: int
    parsing_error_text: str | None


# Composition-friendly type alias for the parser-by-file-type
# resolver. The worker hands ``contexts.ingestion.adapters.outbound.
# parsers.get_parser`` here (or a fake in tests).
ParserResolver = Callable[[str], ParserPort]


async def parse_source(
    *,
    source: Source,
    repository: SourceRepositoryPort,
    parser_resolver: ParserResolver,
) -> ParseResult:
    """Parse a single claimed source and write chunks.

    The caller is responsible for having already claimed the
    source (transitioned it to PARSING via claim_pending_for_parse).
    parse_source completes the state transition: PARSED on success,
    FAILED on ParserError.
    """
    parser = parser_resolver(source.file_type)
    try:
        parsed = parser.parse(source)
    except ParserError as exc:
        await repository.update_source_state(
            source_id=source.id,
            tenant_id=source.tenant_id,
            new_state=SourceState.FAILED,
            parsing_error_text=str(exc),
        )
        return ParseResult(
            source_id=source.id,
            final_state=SourceState.FAILED,
            chunks_written=0,
            parsing_error_text=str(exc),
        )

    now = datetime.now(timezone.utc)
    chunks = [
        Chunk(
            id=uuid4(),
            source_id=source.id,
            tenant_id=source.tenant_id,
            jurisdiction=source.jurisdiction,
            chunk_index=index,
            content=parsed_chunk.content,
            structural_metadata=parsed_chunk.structural_metadata,
            created_at=now,
        )
        for index, parsed_chunk in enumerate(parsed.chunks)
    ]
    await repository.save_chunks(chunks)
    await repository.update_source_state(
        source_id=source.id,
        tenant_id=source.tenant_id,
        new_state=SourceState.PARSED,
    )
    return ParseResult(
        source_id=source.id,
        final_state=SourceState.PARSED,
        chunks_written=len(chunks),
        parsing_error_text=None,
    )
