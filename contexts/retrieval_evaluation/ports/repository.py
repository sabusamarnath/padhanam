"""Write-side port for gold-set authoring (D109).

``GoldSetRepository`` is the write surface invoked by the use cases:
- ``persist_new_gold_set`` atomically inserts the aggregate root and
  its initial draft revision; the FK between gold_sets.current_revision_id
  and gold_set_revisions.id is deferred so the row insertion order
  does not constrain the use case shape.
- ``open_new_draft_revision`` opens a draft revision when the most
  recent revision is finalized and a new authoring session begins.
- ``append_entry`` appends one entry to a draft revision; the draft
  status invariant is enforced at the adapter row-level.
- ``finalize_revision`` transitions a draft to finalized, sets
  ``this_event_hash``, ``previous_event_hash``, ``finalized_at``,
  and updates ``gold_sets.current_revision_id`` in one transaction.

The port stays consumer-defined per D17: the use cases speak the
domain shape; the adapter translates to and from the Postgres row
shape.

Ports layer is pure per D16 — no SQLAlchemy, no asyncpg.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from shared_kernel.tenant_context import TenantContext

from contexts.retrieval_evaluation.domain import (
    GoldSet,
    GoldSetEntry,
    GoldSetRevision,
)


class GoldSetRepository(Protocol):
    """Write-side port for gold-set authoring."""

    async def persist_new_gold_set(
        self,
        *,
        tenant_context: TenantContext,
        gold_set: GoldSet,
        initial_revision: GoldSetRevision,
    ) -> None:
        """Insert the aggregate root and its initial draft revision atomically.

        The FK between gold_sets.current_revision_id and
        gold_set_revisions.id is deferred at the database level so
        both rows insert in a single transaction without a
        placeholder-then-update pattern. The current_revision_id on
        the aggregate row stays NULL until the first revision
        finalizes per the schema invariant in D109's table shape.
        """
        ...

    async def open_new_draft_revision(
        self,
        *,
        tenant_context: TenantContext,
        revision: GoldSetRevision,
    ) -> None:
        """Insert a new draft revision row for an existing gold set."""
        ...

    async def append_entry(
        self,
        *,
        tenant_context: TenantContext,
        entry: GoldSetEntry,
    ) -> None:
        """Append an entry to a draft revision.

        The adapter enforces that the parent revision row's status is
        ``draft``; appending to a finalized revision is a domain
        invariant violation and raises at the adapter boundary.
        """
        ...

    async def finalize_revision(
        self,
        *,
        tenant_context: TenantContext,
        revision_id: UUID,
        gold_set_id: UUID,
        this_event_hash: str,
        previous_event_hash: str,
        finalized_at: datetime,
    ) -> None:
        """Transition a draft revision to finalized and update the aggregate.

        Atomic in one transaction:
        1. UPDATE gold_set_revisions SET status='finalized',
           this_event_hash, previous_event_hash, finalized_at
           WHERE id=:revision_id AND status='draft'.
        2. UPDATE gold_sets SET current_revision_id=:revision_id
           WHERE id=:gold_set_id.

        Raises if the revision is not in draft status (idempotency or
        concurrent-finalization protection).
        """
        ...
