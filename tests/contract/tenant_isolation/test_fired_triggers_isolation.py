"""Tenant isolation contract for the fired_triggers substrate (D24, D147, S54).

The fired_triggers table is tenant-scoped per database-per-tenant
(D32). Two isolation surfaces:

1. **Bound-tenant defence-in-depth at the Postgres adapter.** A
   ``PostgresFiredTriggersAdapter`` bound to tenant A rejects an
   insert_or_skip call carrying tenant B's TenantContext before any
   session resolution — mirroring the messaging Message and intake
   adapters' bound-tenant assertion.

2. **Cross-tenant idempotency-key independence.** The same
   ``(user_id, trigger_type, idempotency_key)`` tuple under two
   different tenants does not collide: tenant A's daily-briefing fire
   for 2026-05-28 must not idempotency-skip tenant B's daily-briefing
   fire for the same date. The UNIQUE constraint scopes by
   ``tenant_id`` as its first column; this scenario pins the
   structural invariant via the in-memory fake (the live Postgres
   path is exercised at the S54 smoke).

D24 requires every adapter touching tenant-scoped data to ship with
tenant_isolation contract scenarios.
"""

from __future__ import annotations

import asyncio

import pytest

from contexts.messaging.adapters.outbound.postgres.fired_triggers_postgres_adapter import (
    PostgresFiredTriggersAdapter,
)
from shared_kernel import TenantContext, TenantId
from tests.unit.contexts.messaging.application._fakes import (
    FakeFiredTriggersRepository,
)


def _ctx(tenant: str) -> TenantContext:
    return TenantContext(
        tenant_id=tenant,
        jurisdiction="eu-west",
        cost_attribution_id=tenant,
    )


async def _unreachable_resolver(_tenant_id: TenantId) -> object:  # noqa: ARG001
    raise AssertionError("resolver must not be reached on bound-tenant reject")


def test_adapter_rejects_cross_tenant_insert() -> None:
    """Adapter bound to tenant-a rejects a tenant-b TenantContext."""
    adapter = PostgresFiredTriggersAdapter(
        per_tenant_sessionmaker_resolver=_unreachable_resolver,
        bound_tenant_id=TenantId("tenant-a"),
    )
    with pytest.raises(ValueError, match="does not match adapter's bound tenant"):
        asyncio.run(
            adapter.insert_or_skip(
                tenant_context=_ctx("tenant-b"),
                user_id="operator-001",
                trigger_type="daily_scheduled",
                idempotency_key="2026-05-28",
            )
        )


def test_same_idempotency_key_across_tenants_does_not_collide() -> None:
    """The same four-tuple-minus-tenant under two tenants both fire fresh."""
    repo = FakeFiredTriggersRepository()

    async def _run() -> tuple[bool, bool]:
        a = await repo.insert_or_skip(
            tenant_context=_ctx("tenant-a"),
            user_id="operator-001",
            trigger_type="daily_scheduled",
            idempotency_key="2026-05-28",
        )
        b = await repo.insert_or_skip(
            tenant_context=_ctx("tenant-b"),
            user_id="operator-001",
            trigger_type="daily_scheduled",
            idempotency_key="2026-05-28",
        )
        return a, b

    a_fresh, b_fresh = asyncio.run(_run())
    assert a_fresh is True
    assert b_fresh is True
    tenants = {row[0] for row in repo.inserted}
    assert tenants == {"tenant-a", "tenant-b"}
