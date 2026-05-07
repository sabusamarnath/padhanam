"""Postgres adapter for SourceRepositoryPort.

Per-tenant Postgres instance per D32; the adapter holds an
``async_sessionmaker`` resolved against the tenant's data plane via
the same per-tenant routing pattern S16's repositories use.

The ``claim_pending_for_parse`` query is the D60-committed queue
mechanism: ``SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1`` against
``state = 'received'`` rows, scoped by tenant_id. The atomic claim
+ state transition happens in a single transaction so concurrent
workers cannot claim the same row. The state transition to
``parsing`` happens inside the same transaction by issuing an
UPDATE with the locked id; SQLAlchemy 2.0 + asyncpg honours the
SKIP LOCKED hint at the asyncpg layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.ingestion.adapters.outbound.postgres._tables import (
    chunks as chunks_table,
    sources as sources_table,
)
from contexts.ingestion.domain.chunk import Chunk
from contexts.ingestion.domain.embedding import Embedding
from contexts.ingestion.domain.source import Source
from contexts.ingestion.domain.state import SourceState


class PostgresSourceRepository:
    """Adapter for SourceRepositoryPort."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        self._session_factory = session_factory

    async def save_source(self, source: Source) -> UUID:
        async with self._session_factory() as session:
            await session.execute(
                sa.insert(sources_table).values(
                    id=str(source.id),
                    tenant_id=source.tenant_id,
                    jurisdiction=source.jurisdiction,
                    file_name=source.file_name,
                    file_type=source.file_type,
                    file_size_bytes=source.file_size_bytes,
                    raw_content=source.raw_content,
                    state=source.state.value,
                    parsing_error_text=source.parsing_error_text,
                    created_by_user_id=source.created_by_user_id,
                    created_at=source.created_at,
                    updated_at=source.updated_at,
                )
            )
            await session.commit()
        return source.id

    async def get_source(
        self, source_id: UUID, tenant_id: str
    ) -> Source | None:
        stmt = sa.select(sources_table).where(
            (sources_table.c.id == str(source_id))
            & (sources_table.c.tenant_id == tenant_id)
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            row = result.mappings().first()
        if row is None:
            return None
        return _row_to_source(row)

    async def claim_pending_for_parse(
        self, tenant_id: str
    ) -> Source | None:
        """Atomic claim of one pending source via SKIP LOCKED.

        The select-then-update happens in a single transaction so
        concurrent workers cannot claim the same row; the
        ``with_for_update(skip_locked=True)`` clause emits the
        Postgres locking hint asyncpg honours.
        """
        select_stmt = (
            sa.select(sources_table)
            .where(
                (sources_table.c.tenant_id == tenant_id)
                & (sources_table.c.state == SourceState.RECEIVED.value)
            )
            .order_by(sources_table.c.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(select_stmt)
                row = result.mappings().first()
                if row is None:
                    return None
                source = _row_to_source(row)
                now = datetime.now(timezone.utc)
                await session.execute(
                    sa.update(sources_table)
                    .where(sources_table.c.id == str(source.id))
                    .values(
                        state=SourceState.PARSING.value,
                        updated_at=now,
                    )
                )
        # Return with state already transitioned so the caller
        # observes the post-transaction shape.
        return Source(
            id=source.id,
            tenant_id=source.tenant_id,
            jurisdiction=source.jurisdiction,
            file_name=source.file_name,
            file_type=source.file_type,
            file_size_bytes=source.file_size_bytes,
            raw_content=source.raw_content,
            state=SourceState.PARSING,
            parsing_error_text=source.parsing_error_text,
            created_by_user_id=source.created_by_user_id,
            created_at=source.created_at,
            updated_at=now,
        )

    async def claim_pending_for_embed(
        self, tenant_id: str
    ) -> Source | None:
        """Atomic claim of one parsed source for embedding (D62).

        Same shape as ``claim_pending_for_parse`` but selects rows
        in ``parsed`` state and transitions them to ``embedding``.
        SKIP LOCKED keeps two workers from claiming the same row.
        """
        select_stmt = (
            sa.select(sources_table)
            .where(
                (sources_table.c.tenant_id == tenant_id)
                & (sources_table.c.state == SourceState.PARSED.value)
            )
            .order_by(sources_table.c.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(select_stmt)
                row = result.mappings().first()
                if row is None:
                    return None
                source = _row_to_source(row)
                now = datetime.now(timezone.utc)
                await session.execute(
                    sa.update(sources_table)
                    .where(sources_table.c.id == str(source.id))
                    .values(
                        state=SourceState.EMBEDDING.value,
                        updated_at=now,
                    )
                )
        return Source(
            id=source.id,
            tenant_id=source.tenant_id,
            jurisdiction=source.jurisdiction,
            file_name=source.file_name,
            file_type=source.file_type,
            file_size_bytes=source.file_size_bytes,
            raw_content=source.raw_content,
            state=SourceState.EMBEDDING,
            parsing_error_text=source.parsing_error_text,
            created_by_user_id=source.created_by_user_id,
            created_at=source.created_at,
            updated_at=now,
            embedding_error_text=source.embedding_error_text,
        )

    async def update_source_state(
        self,
        source_id: UUID,
        tenant_id: str,
        new_state: SourceState,
        parsing_error_text: str | None = None,
        embedding_error_text: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        values: dict[str, object] = {
            "state": new_state.value,
            "updated_at": now,
        }
        # Only overwrite parsing_error_text when transitioning to
        # failed; only overwrite embedding_error_text when
        # transitioning to embedding_failed. Transitions to parsed
        # / embedded clear nothing — leaving the error fields as-is
        # preserves the operator's record of what failed if a row
        # was ever in a failed state. The create-only flow at S19/S20
        # means rows do not re-enter failed-then-parsed, but the
        # discipline holds for future-state tolerance.
        if new_state == SourceState.FAILED:
            values["parsing_error_text"] = parsing_error_text
        if new_state == SourceState.EMBEDDING_FAILED:
            values["embedding_error_text"] = embedding_error_text
        async with self._session_factory() as session:
            await session.execute(
                sa.update(sources_table)
                .where(
                    (sources_table.c.id == str(source_id))
                    & (sources_table.c.tenant_id == tenant_id)
                )
                .values(**values)
            )
            await session.commit()

    async def save_chunks(self, chunks: Sequence[Chunk]) -> None:
        if not chunks:
            return
        rows = [
            {
                "id": str(chunk.id),
                "source_id": str(chunk.source_id),
                "tenant_id": chunk.tenant_id,
                "jurisdiction": chunk.jurisdiction,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "structural_metadata": dict(chunk.structural_metadata),
                "created_at": chunk.created_at or datetime.now(timezone.utc),
            }
            for chunk in chunks
        ]
        async with self._session_factory() as session:
            await session.execute(sa.insert(chunks_table), rows)
            await session.commit()

    async def get_chunks_for_source(
        self, source_id: UUID, tenant_id: str
    ) -> Sequence[Chunk]:
        stmt = (
            sa.select(chunks_table)
            .where(
                (chunks_table.c.source_id == str(source_id))
                & (chunks_table.c.tenant_id == tenant_id)
            )
            .order_by(chunks_table.c.chunk_index.asc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            rows = result.mappings().all()
        return [
            Chunk(
                id=UUID(str(row["id"])),
                source_id=UUID(str(row["source_id"])),
                tenant_id=row["tenant_id"],
                jurisdiction=row["jurisdiction"],
                chunk_index=row["chunk_index"],
                content=row["content"],
                structural_metadata=row["structural_metadata"] or {},
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def upsert_chunk_embeddings(
        self,
        embeddings: Sequence[Embedding],
        tenant_id: str,
    ) -> None:
        """Write per-chunk embedding vectors via UPDATE on chunks.id.

        Per D62: idempotent re-embed via UPDATE — the embedding lives
        on the chunks row itself (single-column shape), so the UPSERT
        semantics collapse to an UPDATE per chunk_id. The pgvector
        cast happens at the SQL boundary because we don't carry the
        pgvector Python binding (the column type ``vector(768)`` is
        the architectural authority on dimension; mismatches surface
        as Postgres errors rather than silently-truncated vectors).
        Tenant-scoped: the WHERE clause pins tenant_id so a cross-
        tenant Embedding (which would be a worker bug) cannot land.
        """
        if not embeddings:
            return
        update_stmt = sa.text(
            "UPDATE chunks SET embedding = CAST(:vector AS vector) "
            "WHERE id = :chunk_id AND tenant_id = :tenant_id"
        )
        async with self._session_factory() as session:
            for embedding in embeddings:
                await session.execute(
                    update_stmt,
                    {
                        "vector": _format_vector_literal(embedding.vector),
                        "chunk_id": str(embedding.chunk_id),
                        "tenant_id": tenant_id,
                    },
                )
            await session.commit()

    async def count_embedded_chunks(
        self, source_id: UUID, tenant_id: str
    ) -> int:
        stmt = sa.text(
            "SELECT COUNT(*) FROM chunks "
            "WHERE source_id = :source_id AND tenant_id = :tenant_id "
            "AND embedding IS NOT NULL"
        )
        async with self._session_factory() as session:
            result = await session.execute(
                stmt,
                {
                    "source_id": str(source_id),
                    "tenant_id": tenant_id,
                },
            )
            count = result.scalar_one()
        return int(count)


def _format_vector_literal(vector) -> str:
    """Format a list of floats as a pgvector text literal.

    pgvector accepts the literal ``'[v1,v2,...]'`` cast to ``vector``
    via ``CAST(... AS vector)`` or ``::vector``. Avoids needing the
    pgvector Python binding (``pgvector.sqlalchemy.Vector`` requires
    asyncpg codec registration, which is a wider dep surface than the
    text-literal path warrants at S20). The dimension is enforced at
    the column type, not at the Python layer.
    """
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"


def _row_to_source(row) -> Source:
    return Source(
        id=UUID(str(row["id"])),
        tenant_id=row["tenant_id"],
        jurisdiction=row["jurisdiction"],
        file_name=row["file_name"],
        file_type=row["file_type"],
        file_size_bytes=row["file_size_bytes"],
        raw_content=bytes(row["raw_content"]) if row["raw_content"] is not None else b"",
        state=SourceState(row["state"]),
        parsing_error_text=row["parsing_error_text"],
        created_by_user_id=row["created_by_user_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        embedding_error_text=row.get("embedding_error_text"),
    )
