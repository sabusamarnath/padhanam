"""Read-side port for the gold-set surface (consumer-defined per D17).

``GoldSetReader`` is consumed by the application use cases (read-
side and write-side reads-before-writes) and by the future
optimization context at S41. Consumer-defined per D17: the consuming
code shapes the port's surface against its own DTO needs; the
adapter translates from the Postgres row shape.

Ports layer is pure per D16 — no SQLAlchemy, no asyncpg.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from shared_kernel.tenant_context import TenantContext

from contexts.retrieval_evaluation.domain import (
    GoldSet,
    GoldSetEntry,
    GoldSetRevision,
)
from contexts.retrieval_evaluation.domain.query_filters import (
    GoldSetListCursor,
)


@dataclass(frozen=True)
class GoldSetListPage:
    """One page of ``list_gold_sets`` output."""

    gold_sets: tuple[GoldSet, ...]
    next_cursor: GoldSetListCursor | None


@dataclass(frozen=True)
class GoldSetWithCurrentRevision:
    """Aggregate snapshot returned by ``get_gold_set_with_current_revision``.

    ``current_revision`` is None when the gold set has no finalized
    revision yet (i.e., authoring is in progress on the initial draft
    and no finalize has fired). ``entries`` carries the entries of the
    current finalized revision when present, sorted by entry_index.
    """

    gold_set: GoldSet
    current_revision: GoldSetRevision | None
    entries: tuple[GoldSetEntry, ...]


@dataclass(frozen=True)
class RevisionWithEntries:
    """Revision snapshot returned by ``get_revision_with_entries``."""

    revision: GoldSetRevision
    entries: tuple[GoldSetEntry, ...]


class GoldSetReader(Protocol):
    """Read-side port for gold-set queries."""

    async def list_gold_sets(
        self,
        *,
        tenant_context: TenantContext,
        cursor: GoldSetListCursor | None,
        page_size: int,
    ) -> GoldSetListPage:
        """List gold sets for a tenant, paginated (created_at DESC, id DESC).

        The cursor is None on the first page; subsequent pages pass
        the prior page's next_cursor verbatim.
        """
        ...

    async def get_gold_set_with_current_revision(
        self,
        *,
        tenant_context: TenantContext,
        gold_set_id: UUID,
    ) -> GoldSetWithCurrentRevision | None:
        """Read aggregate + current finalized revision + its entries.

        Returns None when the gold set does not exist or belongs to a
        different tenant (tenant_isolation contract).
        """
        ...

    async def get_revision_with_entries(
        self,
        *,
        tenant_context: TenantContext,
        revision_id: UUID,
    ) -> RevisionWithEntries | None:
        """Read a specific revision plus its entries (in entry_index order).

        Returns None on cross-tenant access or missing revision.
        """
        ...

    async def find_current_draft_revision(
        self,
        *,
        tenant_context: TenantContext,
        gold_set_id: UUID,
    ) -> GoldSetRevision | None:
        """Return the current draft revision for a gold set, or None.

        Used by the append_entry use case to locate the draft to
        append to (and by finalize_revision to find the row to
        transition).
        """
        ...
