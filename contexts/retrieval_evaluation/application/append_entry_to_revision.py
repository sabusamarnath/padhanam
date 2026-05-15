"""append_entry_to_revision use case (D109 commitment 6).

Appends one entry to the current draft revision. If the gold set's
most recent revision is finalized (no current draft), opens a new
draft via ``open_new_draft_revision`` first and appends to it; this
matches D109 commitment 6's "opens a new draft revision if
subsequent edits arrive" semantics: drafts open lazily when an
edit fires rather than eagerly at finalize-time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from shared_kernel.tenant_context import TenantContext

from contexts.retrieval_evaluation.domain import (
    GoldSetEntry,
    GoldSetRevision,
    GoldSetRevisionStatus,
)
from contexts.retrieval_evaluation.ports.reader import GoldSetReader
from contexts.retrieval_evaluation.ports.repository import GoldSetRepository


class GoldSetNotFoundError(LookupError):
    """Raised when the gold set does not exist for the tenant."""


@dataclass(frozen=True)
class AppendEntryResult:
    revision: GoldSetRevision
    entry: GoldSetEntry
    opened_new_draft: bool


async def append_entry_to_revision(
    *,
    tenant_context: TenantContext,
    gold_set_id: UUID,
    query: str,
    expected_chunk_ids: tuple[UUID, ...],
    created_by_user_id: str,
    reader: GoldSetReader,
    repository: GoldSetRepository,
    now: datetime | None = None,
) -> AppendEntryResult:
    """Append an entry, opening a new draft revision if none exists."""
    created_at = now or datetime.now(timezone.utc)

    current_draft = await reader.find_current_draft_revision(
        tenant_context=tenant_context,
        gold_set_id=gold_set_id,
    )

    opened_new_draft = False
    if current_draft is None:
        snapshot = await reader.get_gold_set_with_current_revision(
            tenant_context=tenant_context,
            gold_set_id=gold_set_id,
        )
        if snapshot is None:
            raise GoldSetNotFoundError(
                f"gold set {gold_set_id} not found for tenant"
            )
        last_finalized = snapshot.current_revision
        next_revision_number = (
            last_finalized.revision_number + 1 if last_finalized else 1
        )
        current_draft = GoldSetRevision(
            id=uuid4(),
            gold_set_id=gold_set_id,
            revision_number=next_revision_number,
            status=GoldSetRevisionStatus.DRAFT,
            created_by_user_id=created_by_user_id,
            created_at=created_at,
            finalized_at=None,
            this_event_hash=None,
            previous_event_hash=None,
        )
        await repository.open_new_draft_revision(
            tenant_context=tenant_context,
            revision=current_draft,
        )
        opened_new_draft = True

    existing = await reader.get_revision_with_entries(
        tenant_context=tenant_context,
        revision_id=current_draft.id,
    )
    next_entry_index = len(existing.entries) if existing else 0

    entry = GoldSetEntry(
        id=uuid4(),
        gold_set_revision_id=current_draft.id,
        entry_index=next_entry_index,
        query=query,
        expected_chunk_ids=expected_chunk_ids,
    )
    await repository.append_entry(
        tenant_context=tenant_context,
        entry=entry,
    )
    return AppendEntryResult(
        revision=current_draft,
        entry=entry,
        opened_new_draft=opened_new_draft,
    )
