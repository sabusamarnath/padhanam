"""get_gold_set use case (D109 commitment 6).

Thin pass-through to ``GoldSetReader.get_gold_set_with_current_revision``.
Returns the aggregate snapshot (gold-set, current finalized revision
if any, entries of that revision) for a single gold-set id under the
tenant context. Cross-tenant reads return None per the reader port's
tenant-isolation contract.
"""

from __future__ import annotations

from uuid import UUID

from shared_kernel.tenant_context import TenantContext

from contexts.retrieval_evaluation.ports.reader import (
    GoldSetReader,
    GoldSetWithCurrentRevision,
)


async def get_gold_set(
    *,
    tenant_context: TenantContext,
    gold_set_id: UUID,
    reader: GoldSetReader,
) -> GoldSetWithCurrentRevision | None:
    return await reader.get_gold_set_with_current_revision(
        tenant_context=tenant_context,
        gold_set_id=gold_set_id,
    )
