"""Unit tests for the parse_source use case.

Uses an in-memory fake repository plus fake parser to cover the
worker-side state-transition contract per D60: PARSED on success
(chunks written), FAILED on ParserError (chunks not written,
parsing_error_text populated).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID, uuid4

from contexts.ingestion.application.parse_source import parse_source
from contexts.ingestion.domain.chunk import Chunk
from contexts.ingestion.domain.parsed_content import ParsedChunk, ParsedContent
from contexts.ingestion.domain.source import Source
from contexts.ingestion.domain.state import SourceState
from contexts.ingestion.ports.parser_port import ParserError


class _FakeRepo:
    def __init__(self) -> None:
        self.saved_chunks: list[Chunk] = []
        self.state_updates: list[
            tuple[UUID, str, SourceState, str | None]
        ] = []

    async def save_source(self, source: Source) -> UUID:  # pragma: no cover
        return source.id

    async def get_source(self, source_id, tenant_id):  # pragma: no cover
        return None

    async def claim_pending_for_parse(self, tenant_id):  # pragma: no cover
        return None

    async def update_source_state(
        self, source_id, tenant_id, new_state, parsing_error_text=None
    ):
        self.state_updates.append(
            (source_id, tenant_id, new_state, parsing_error_text)
        )

    async def save_chunks(self, chunks: Sequence[Chunk]) -> None:
        self.saved_chunks.extend(chunks)


class _FakeParser:
    def __init__(self, parsed: ParsedContent) -> None:
        self._parsed = parsed

    def parse(self, source: Source) -> ParsedContent:
        return self._parsed


class _FailingParser:
    def parse(self, source: Source) -> ParsedContent:
        raise ParserError("synthetic parser failure")


def _source(state: SourceState = SourceState.PARSING) -> Source:
    now = datetime.now(timezone.utc)
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
        created_by_user_id="u1",
        created_at=now,
        updated_at=now,
    )


def _run(coro):
    return asyncio.run(coro)


def test_parse_source_success_writes_chunks_and_marks_parsed() -> None:
    parsed = ParsedContent(
        chunks=(
            ParsedChunk(content="chunk one", structural_metadata={"k": 1}),
            ParsedChunk(content="chunk two", structural_metadata={"k": 2}),
        )
    )
    repo = _FakeRepo()
    src = _source()

    result = _run(
        parse_source(
            source=src,
            repository=repo,
            parser_resolver=lambda ft: _FakeParser(parsed),
        )
    )

    assert result.final_state == SourceState.PARSED
    assert result.chunks_written == 2
    assert result.parsing_error_text is None
    assert len(repo.saved_chunks) == 2
    # Chunks carry positional indices.
    assert repo.saved_chunks[0].chunk_index == 0
    assert repo.saved_chunks[1].chunk_index == 1
    # State transition recorded once, to PARSED.
    assert len(repo.state_updates) == 1
    src_id, tenant, new_state, error_text = repo.state_updates[0]
    assert src_id == src.id
    assert tenant == src.tenant_id
    assert new_state == SourceState.PARSED
    assert error_text is None


def test_parse_source_parser_error_marks_failed_and_writes_no_chunks() -> None:
    repo = _FakeRepo()
    src = _source()

    result = _run(
        parse_source(
            source=src,
            repository=repo,
            parser_resolver=lambda ft: _FailingParser(),
        )
    )

    assert result.final_state == SourceState.FAILED
    assert result.chunks_written == 0
    assert "synthetic" in result.parsing_error_text
    assert repo.saved_chunks == []
    # Single state update to FAILED with the error text populated.
    assert len(repo.state_updates) == 1
    _, _, new_state, error_text = repo.state_updates[0]
    assert new_state == SourceState.FAILED
    assert "synthetic" in error_text


def test_parse_source_empty_parsed_content_marks_parsed_zero_chunks() -> None:
    """A parser that returns no chunks (e.g., empty file) still
    transitions the source to PARSED. The save_chunks call with an
    empty sequence is a no-op at the adapter layer; the use case
    contract is "if parsing succeeded, mark parsed regardless of
    chunk count" so an empty source is observed as parsed-with-
    zero-chunks rather than stuck in parsing.
    """
    repo = _FakeRepo()
    src = _source()
    result = _run(
        parse_source(
            source=src,
            repository=repo,
            parser_resolver=lambda ft: _FakeParser(ParsedContent(chunks=())),
        )
    )
    assert result.final_state == SourceState.PARSED
    assert result.chunks_written == 0
    assert repo.saved_chunks == []
    assert len(repo.state_updates) == 1
    assert repo.state_updates[0][2] == SourceState.PARSED


def test_parse_source_resolver_called_with_source_file_type() -> None:
    """Sanity check that parser dispatch uses source.file_type
    rather than something else (e.g., the file_name extension).
    """
    captured: list[str] = []

    def _resolver(file_type: str):
        captured.append(file_type)
        return _FakeParser(ParsedContent(chunks=()))

    src = _source()
    repo = _FakeRepo()
    _run(
        parse_source(
            source=src,
            repository=repo,
            parser_resolver=_resolver,
        )
    )
    assert captured == [src.file_type]
