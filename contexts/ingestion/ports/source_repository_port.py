"""SourceRepositoryPort — read/write access for sources and chunks.

The upload-side use case (``register_source``), the parse worker
use case (``parse_source``), and the embed worker use case
(``embed_source``) all call through here. Per-tenant routing is
the adapter's responsibility: the Postgres adapter holds an
``async_sessionmaker`` resolved against the tenant's data plane via
the tenancy context's session-factory cache (D36) — the same
pattern S16's evaluation repositories established.

Methods at S20:

  - ``save_source``: persist a new Source row in ``received`` state.
  - ``get_source``: read a single Source by id, tenant-scoped.
  - ``claim_pending_for_parse``: atomic claim of a single pending
    source via SKIP LOCKED against ``received`` rows; transitions
    to ``parsing``.
  - ``claim_pending_for_embed``: same shape against ``parsed`` rows
    per D62; transitions to ``embedding``. Two per-stage methods
    rather than one parameterised method per the D62 reasoning —
    each stage's claim has its own state-transition target and
    keeps the SQL legible at the call site.
  - ``update_source_state``: transition a source state; populate
    ``parsing_error_text`` when transitioning to ``failed`` or
    ``embedding_error_text`` when transitioning to
    ``embedding_failed``.
  - ``save_chunks``: persist the chunks produced by the parser.
  - ``get_chunks_for_source``: load all chunks for a source so the
    embed use case can hand them to the embedder.
  - ``upsert_chunk_embeddings``: write per-chunk embedding vectors
    via UPDATE on ``chunks.id`` per D62's idempotent re-embed
    commitment. Re-running the embedding stage replaces the vector
    rather than producing a duplicate row.
  - ``count_embedded_chunks``: structural assertion helper for the
    integration test; counts chunks with non-null ``embedding`` for
    a source, tenant-scoped.
"""

from __future__ import annotations

from typing import Protocol, Sequence
from uuid import UUID

from contexts.ingestion.domain.chunk import Chunk
from contexts.ingestion.domain.embedding import Embedding
from contexts.ingestion.domain.source import Source
from contexts.ingestion.domain.state import SourceState


class SourceRepositoryPort(Protocol):
    async def save_source(self, source: Source) -> UUID:
        """Persist a new Source row; return its id."""
        ...

    async def get_source(self, source_id: UUID, tenant_id: str) -> Source | None:
        """Read a single Source by id, scoped to the tenant."""
        ...

    async def claim_pending_for_parse(
        self, tenant_id: str
    ) -> Source | None:
        """Atomically claim one pending source for parsing.

        Uses ``SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1`` against
        rows in ``received`` state for the given tenant; transitions
        the row to ``parsing`` in the same transaction and returns
        the loaded Source. Returns None if no rows are claimable.
        """
        ...

    async def claim_pending_for_embed(
        self, tenant_id: str
    ) -> Source | None:
        """Atomically claim one parsed source for embedding (D62).

        Same SKIP LOCKED shape as the parse claim; selects rows in
        ``parsed`` state and transitions them to ``embedding``
        within the same transaction.
        """
        ...

    async def update_source_state(
        self,
        source_id: UUID,
        tenant_id: str,
        new_state: SourceState,
        parsing_error_text: str | None = None,
        embedding_error_text: str | None = None,
    ) -> None:
        """Transition a source's state.

        Sets ``parsing_error_text`` only when transitioning to
        ``failed``; sets ``embedding_error_text`` only when
        transitioning to ``embedding_failed``. Other transitions
        leave both error fields untouched.
        """
        ...

    async def save_chunks(self, chunks: Sequence[Chunk]) -> None:
        """Persist the chunks produced by the parser."""
        ...

    async def get_chunks_for_source(
        self, source_id: UUID, tenant_id: str
    ) -> Sequence[Chunk]:
        """Load all chunks for a source in chunk_index order.

        Tenant-scoped: only chunks for the given tenant are
        returned, preserving D24's tenant-isolation invariant on
        the read path. Used by ``embed_source`` to fetch the
        parsed chunks the embedder operates on.
        """
        ...

    async def upsert_chunk_embeddings(
        self,
        embeddings: Sequence[Embedding],
        tenant_id: str,
    ) -> None:
        """Write per-chunk embedding vectors via UPDATE on chunks.id.

        Idempotent per D62: re-running the embed stage replaces the
        vector for each chunk_id rather than producing a duplicate
        row. Tenant-scoped: the WHERE clause includes tenant_id so
        cross-tenant writes raise a structural mismatch rather than
        silently updating the wrong row.
        """
        ...

    async def count_embedded_chunks(
        self, source_id: UUID, tenant_id: str
    ) -> int:
        """Return the count of chunks with a non-null embedding for
        the source. Tenant-scoped. Helper for integration-test
        assertions about the worker's embedding-write effect.
        """
        ...
