"""Unit tests for the register_source use case.

Uses an in-memory fake repository so the test exercises the use
case logic without touching Postgres. Adapter behaviour is
exercised by the worker integration test against the live tenant_a
data plane.
"""

from __future__ import annotations

import asyncio
from typing import Sequence
from uuid import UUID

import pytest

from contexts.ingestion.application.register_source import (
    UnsupportedFileTypeError,
    register_source,
)
from contexts.ingestion.domain.chunk import Chunk
from contexts.ingestion.domain.source import Source
from contexts.ingestion.domain.state import SourceState


class _InMemoryRepo:
    def __init__(self) -> None:
        self.saved: list[Source] = []

    async def save_source(self, source: Source) -> UUID:
        self.saved.append(source)
        return source.id

    # Stubs so the type-checker is happy if a future test reuses
    # this fake against the worker-side use case.
    async def get_source(self, source_id, tenant_id):  # pragma: no cover
        for s in self.saved:
            if s.id == source_id and s.tenant_id == tenant_id:
                return s
        return None

    async def claim_pending_for_parse(self, tenant_id):  # pragma: no cover
        for s in self.saved:
            if s.tenant_id == tenant_id and s.state == SourceState.RECEIVED:
                return s
        return None

    async def update_source_state(  # pragma: no cover
        self, source_id, tenant_id, new_state, parsing_error_text=None
    ):
        return None

    async def save_chunks(self, chunks: Sequence[Chunk]) -> None:  # pragma: no cover
        return None


def _run(coro):
    return asyncio.run(coro)


def test_register_source_persists_in_received_state() -> None:
    repo = _InMemoryRepo()
    source_id = _run(
        register_source(
            repository=repo,
            tenant_id="tenant-a",
            jurisdiction="eu-west",
            file_name="x.md",
            file_type="markdown",
            raw_content=b"# hi\n\nbody",
            created_by_user_id="user-1",
        )
    )
    assert isinstance(source_id, UUID)
    assert len(repo.saved) == 1
    saved = repo.saved[0]
    assert saved.id == source_id
    assert saved.state == SourceState.RECEIVED
    assert saved.tenant_id == "tenant-a"
    assert saved.jurisdiction == "eu-west"
    assert saved.file_name == "x.md"
    assert saved.file_type == "markdown"
    assert saved.file_size_bytes == len(b"# hi\n\nbody")
    assert saved.raw_content == b"# hi\n\nbody"
    assert saved.parsing_error_text is None
    assert saved.created_by_user_id == "user-1"


def test_register_source_rejects_unsupported_file_type() -> None:
    repo = _InMemoryRepo()
    with pytest.raises(UnsupportedFileTypeError) as exc_info:
        _run(
            register_source(
                repository=repo,
                tenant_id="tenant-a",
                jurisdiction="eu-west",
                file_name="x.pdf",
                file_type="pdf",
                raw_content=b"%PDF-1.4",
                created_by_user_id="user-1",
            )
        )
    assert "pdf" in str(exc_info.value)
    assert "D61" in str(exc_info.value)
    assert repo.saved == []


def test_register_source_records_actual_size_from_bytes() -> None:
    """file_size_bytes is computed from the bytes the use case
    receives. The CLI is responsible for passing the right bytes;
    this assertion fences the use case against caller drift."""
    repo = _InMemoryRepo()
    raw = b"a" * 1024
    _run(
        register_source(
            repository=repo,
            tenant_id="tenant-a",
            jurisdiction="eu-west",
            file_name="big.txt",
            file_type="text",
            raw_content=raw,
            created_by_user_id="user-1",
        )
    )
    assert repo.saved[0].file_size_bytes == 1024


def test_register_source_supports_text_file_type() -> None:
    """Sanity check for the second supported type at S19."""
    repo = _InMemoryRepo()
    _run(
        register_source(
            repository=repo,
            tenant_id="tenant-a",
            jurisdiction="eu-west",
            file_name="notes.txt",
            file_type="text",
            raw_content=b"hello\n\nworld",
            created_by_user_id="user-1",
        )
    )
    assert repo.saved[0].file_type == "text"
