"""finalize_revision use case (D109 commitment 6).

Marks the current draft revision finalized, computes
``this_event_hash`` via the platform hash-chain primitive (chained
from the prior finalized revision or GENESIS_REVISION_HASH for
revision-1), and updates ``gold_sets.current_revision_id`` to point
at the newly-finalized revision. The repository performs the
transition + aggregate-update in one transaction.

Raises ``NoDraftToFinalizeError`` when the gold set has no current
draft (already finalized or never created).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from shared_kernel.tenant_context import TenantContext

from contexts.retrieval_evaluation.domain import (
    GENESIS_REVISION_HASH,
    GoldSetRevision,
    GoldSetRevisionStatus,
    compute_revision_hash,
)
from contexts.retrieval_evaluation.ports.reader import GoldSetReader
from contexts.retrieval_evaluation.ports.repository import GoldSetRepository


class NoDraftToFinalizeError(LookupError):
    """Raised when no current draft revision exists for the gold set."""


class EmptyDraftError(ValueError):
    """Raised when a draft revision carries no entries to finalize."""


@dataclass(frozen=True)
class FinalizeRevisionResult:
    revision: GoldSetRevision
    this_event_hash: str
    previous_event_hash: str


async def finalize_revision(
    *,
    tenant_context: TenantContext,
    gold_set_id: UUID,
    reader: GoldSetReader,
    repository: GoldSetRepository,
    now: datetime | None = None,
) -> FinalizeRevisionResult:
    finalized_at = now or datetime.now(timezone.utc)

    draft = await reader.find_current_draft_revision(
        tenant_context=tenant_context,
        gold_set_id=gold_set_id,
    )
    if draft is None:
        raise NoDraftToFinalizeError(
            f"gold set {gold_set_id} has no current draft revision"
        )

    revision_with_entries = await reader.get_revision_with_entries(
        tenant_context=tenant_context,
        revision_id=draft.id,
    )
    if revision_with_entries is None or not revision_with_entries.entries:
        raise EmptyDraftError(
            f"draft revision {draft.id} has no entries; cannot finalize"
        )

    snapshot = await reader.get_gold_set_with_current_revision(
        tenant_context=tenant_context,
        gold_set_id=gold_set_id,
    )
    prior_finalized = snapshot.current_revision if snapshot else None
    previous_event_hash = (
        prior_finalized.this_event_hash
        if prior_finalized and prior_finalized.this_event_hash
        else GENESIS_REVISION_HASH
    )

    this_event_hash = compute_revision_hash(
        revision_number=draft.revision_number,
        entries=revision_with_entries.entries,
        previous_event_hash=previous_event_hash,
    )

    await repository.finalize_revision(
        tenant_context=tenant_context,
        revision_id=draft.id,
        gold_set_id=gold_set_id,
        this_event_hash=this_event_hash,
        previous_event_hash=previous_event_hash,
        finalized_at=finalized_at,
    )

    finalized_revision = GoldSetRevision(
        id=draft.id,
        gold_set_id=draft.gold_set_id,
        revision_number=draft.revision_number,
        status=GoldSetRevisionStatus.FINALIZED,
        created_by_user_id=draft.created_by_user_id,
        created_at=draft.created_at,
        finalized_at=finalized_at,
        this_event_hash=this_event_hash,
        previous_event_hash=previous_event_hash,
    )
    return FinalizeRevisionResult(
        revision=finalized_revision,
        this_event_hash=this_event_hash,
        previous_event_hash=previous_event_hash,
    )
