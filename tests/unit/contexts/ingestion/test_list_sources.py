"""Unit tests for the list_sources application use case (D104, S38).

Mirror of the get_source unit test shape: a fake SourceRepositoryPort
returns a deterministic SourceListPage, the use case is exercised
through its keyword-only signature, and the resulting page is
asserted on. The use case is signature-thin so the test surface
narrows on parameter forwarding.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID, uuid4

from contexts.ingestion.application.list_sources import list_sources
from contexts.ingestion.domain.chunk import Chunk
from contexts.ingestion.domain.embedding import Embedding
from contexts.ingestion.domain.source import Source
from contexts.ingestion.domain.source_list import (
    SourceListCursor,
    SourceListPage,
)
from contexts.ingestion.domain.state import SourceState


class _FakeRepository:
    """Records list_sources kwargs; returns the configured page."""

    def __init__(self, page: SourceListPage) -> None:
        self.page = page
        self.calls: list[dict[str, object]] = []

    # Required by the SourceRepositoryPort Protocol — no-op stubs.
    async def save_source(self, source: Source) -> UUID:  # pragma: no cover
        return source.id

    async def get_source(
        self, source_id: UUID, tenant_id: str
    ) -> Source | None:  # pragma: no cover
        return None

    async def claim_pending_for_parse(self, tenant_id: str) -> Source | None:  # pragma: no cover
        return None

    async def claim_pending_for_embed(self, tenant_id: str) -> Source | None:  # pragma: no cover
        return None

    async def claim_pending_for_extract(self, tenant_id: str) -> Source | None:  # pragma: no cover
        return None

    async def update_source_state(
        self,
        source_id: UUID,
        tenant_id: str,
        new_state: SourceState,
        parsing_error_text: str | None = None,
        embedding_error_text: str | None = None,
        extraction_error_text: str | None = None,
    ) -> None:  # pragma: no cover
        return None

    async def save_chunks(self, chunks: Sequence[Chunk]) -> None:  # pragma: no cover
        return None

    async def get_chunks_for_source(
        self, source_id: UUID, tenant_id: str
    ) -> Sequence[Chunk]:  # pragma: no cover
        return []

    async def upsert_chunk_embeddings(
        self,
        embeddings: Sequence[Embedding],
        tenant_id: str,
    ) -> None:  # pragma: no cover
        return None

    async def count_embedded_chunks(
        self, source_id: UUID, tenant_id: str
    ) -> int:  # pragma: no cover
        return 0

    async def list_sources(
        self,
        *,
        tenant_id: str,
        cursor: SourceListCursor | None,
        page_size: int,
    ) -> SourceListPage:
        self.calls.append(
            {"tenant_id": tenant_id, "cursor": cursor, "page_size": page_size}
        )
        return self.page


def _make_source(tenant_id: str = "tenant-a") -> Source:
    now = datetime(2026, 5, 14, 10, 30, tzinfo=timezone.utc)
    return Source(
        id=uuid4(),
        tenant_id=tenant_id,
        jurisdiction="UK",
        file_name="example.md",
        file_type="md",
        file_size_bytes=42,
        raw_content=b"# example",
        state=SourceState.INDEXED,
        parsing_error_text=None,
        created_by_user_id="user-1",
        created_at=now,
        updated_at=now,
    )


def test_list_sources_forwards_to_repository() -> None:
    source = _make_source()
    expected_page = SourceListPage(sources=(source,), next_cursor=None)
    repo = _FakeRepository(expected_page)

    page = asyncio.run(
        list_sources(
            repository=repo,
            tenant_id="tenant-a",
            cursor=None,
            page_size=10,
        )
    )

    assert page is expected_page
    assert repo.calls == [
        {"tenant_id": "tenant-a", "cursor": None, "page_size": 10}
    ]


def test_list_sources_forwards_cursor_through() -> None:
    cursor = SourceListCursor(
        created_at=datetime(2026, 5, 14, 10, 0, tzinfo=timezone.utc),
        id=uuid4(),
        page_size=10,
    )
    repo = _FakeRepository(SourceListPage(sources=(), next_cursor=None))

    asyncio.run(
        list_sources(
            repository=repo,
            tenant_id="tenant-b",
            cursor=cursor,
            page_size=10,
        )
    )

    assert repo.calls[0]["cursor"] is cursor
    assert repo.calls[0]["tenant_id"] == "tenant-b"


def test_list_sources_default_page_size_50() -> None:
    repo = _FakeRepository(SourceListPage(sources=(), next_cursor=None))

    asyncio.run(list_sources(repository=repo, tenant_id="tenant-c"))

    assert repo.calls[0]["page_size"] == 50
