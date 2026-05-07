"""SourceRepositoryPort — read/write access for sources and chunks.

The upload-side use case (``register_source``) and the worker-side
use case (``parse_source``) call through here. Per-tenant routing
is the adapter's responsibility: the Postgres adapter holds an
``async_sessionmaker`` resolved against the tenant's data plane via
the tenancy context's session-factory cache (D36) — the same
pattern S16's evaluation repositories established.

Methods at S19:

  - ``save_source``: persist a new Source row in ``received`` state.
    Used by ``register_source``. Returns the persisted source id
    (UUID).

  - ``get_source``: read a single Source by id. Used by both the
    register-side use case (idempotency check; not exercised at
    S19's create-only flow) and the parse-side use case (after
    claim, to load the row for the parser).

  - ``claim_pending_for_parse``: atomic claim of a single pending
    source via ``SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1`` per
    D60's queue commitment. Returns the claimed Source with its
    state already transitioned to ``parsing`` and the row updated
    in the same transaction; concurrent workers get None for that
    row. Tenant-scoped: only rows for the given tenant are
    candidates.

  - ``update_source_state``: transition a source to ``parsed`` or
    ``failed``. Bumps ``updated_at``; sets ``parsing_error_text``
    when transitioning to failed.

  - ``save_chunks``: persist the chunks produced by the parser. The
    UNIQUE(source_id, chunk_index) constraint per D61 is the
    structural backstop; the worker's idempotency contract per D60
    means the parser write only happens once per source-index pair.
"""

from __future__ import annotations

from typing import Protocol, Sequence
from uuid import UUID

from contexts.ingestion.domain.chunk import Chunk
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

    async def update_source_state(
        self,
        source_id: UUID,
        tenant_id: str,
        new_state: SourceState,
        parsing_error_text: str | None = None,
    ) -> None:
        """Transition a source's state; populate parsing_error_text
        when transitioning to ``failed``.
        """
        ...

    async def save_chunks(self, chunks: Sequence[Chunk]) -> None:
        """Persist the chunks produced by the parser.

        Atomic per source: the worker invokes this within the same
        transaction as the state transition to ``parsed`` so that a
        partial chunk-write does not leave the row marked parsed.
        """
        ...
