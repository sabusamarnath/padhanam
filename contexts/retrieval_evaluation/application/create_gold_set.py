"""create_gold_set use case (D109 commitment 6).

Creates a gold-set aggregate root plus an initial draft revision in
a single transaction via ``GoldSetRepository.persist_new_gold_set``.
The initial revision has revision_number=1, status=draft, and no
hash fields (hashes land at finalize_revision time per D109
commitment 4). gold_sets.current_revision_id is NULL until the
first revision finalizes per the schema invariant.

The use case takes a tenant context and returns the persisted
aggregate snapshot for the caller (CLI surface at S39 commit 8;
HTTP transport at S42).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from shared_kernel.tenant_context import TenantContext

from contexts.retrieval_evaluation.domain import (
    GoldSet,
    GoldSetRevision,
    GoldSetRevisionStatus,
)
from contexts.retrieval_evaluation.ports.repository import GoldSetRepository


@dataclass(frozen=True)
class CreateGoldSetResult:
    gold_set: GoldSet
    initial_revision: GoldSetRevision


async def create_gold_set(
    *,
    tenant_context: TenantContext,
    name: str,
    created_by_user_id: str,
    repository: GoldSetRepository,
    now: datetime | None = None,
) -> CreateGoldSetResult:
    """Persist a new gold set with an initial draft revision."""
    created_at = now or datetime.now(timezone.utc)
    gold_set_id = uuid4()
    revision_id = uuid4()

    gold_set = GoldSet(
        id=gold_set_id,
        tenant_id=UUID(tenant_context.tenant_id),
        jurisdiction=tenant_context.jurisdiction,
        name=name,
        created_by_user_id=created_by_user_id,
        created_at=created_at,
        current_revision_id=None,
    )
    initial_revision = GoldSetRevision(
        id=revision_id,
        gold_set_id=gold_set_id,
        revision_number=1,
        status=GoldSetRevisionStatus.DRAFT,
        created_by_user_id=created_by_user_id,
        created_at=created_at,
        finalized_at=None,
        this_event_hash=None,
        previous_event_hash=None,
    )

    await repository.persist_new_gold_set(
        tenant_context=tenant_context,
        gold_set=gold_set,
        initial_revision=initial_revision,
    )
    return CreateGoldSetResult(gold_set=gold_set, initial_revision=initial_revision)
