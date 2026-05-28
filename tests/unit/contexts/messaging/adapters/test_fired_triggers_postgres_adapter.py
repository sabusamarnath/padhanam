"""Unit tests for PostgresFiredTriggersAdapter (D147, S54).

The SQL execution (INSERT ... ON CONFLICT DO NOTHING; rowcount-based
fresh-vs-conflict) is verified at the live-stack smoke (commit 7).
These unit tests pin the bound-tenant defence-in-depth assertion,
which raises before any session is resolved — so the test needs no
Postgres.

The race-safe insert-or-skip semantics are exercised at the
application altitude via FakeFiredTriggersRepository in the FireTrigger
use-case unit tests (commit 4) and structurally at the tenant_isolation
contract harness.
"""

from __future__ import annotations

import asyncio

import pytest

from contexts.messaging.adapters.outbound.postgres.fired_triggers_postgres_adapter import (
    PostgresFiredTriggersAdapter,
)
from shared_kernel import TenantContext, TenantId


async def _unreachable_resolver(_tenant_id: TenantId) -> object:  # noqa: ARG001
    raise AssertionError(
        "resolver must not be reached when the bound-tenant assertion fails"
    )


def _adapter(bound: str) -> PostgresFiredTriggersAdapter:
    return PostgresFiredTriggersAdapter(
        per_tenant_sessionmaker_resolver=_unreachable_resolver,
        bound_tenant_id=TenantId(bound),
    )


def test_insert_or_skip_rejects_cross_tenant_context() -> None:
    """A TenantContext for a different tenant raises before any DB call."""
    adapter = _adapter("tenant-a")
    foreign_context = TenantContext(
        tenant_id="tenant-b",
        jurisdiction="eu-west",
        cost_attribution_id="tenant-b",
    )
    with pytest.raises(ValueError, match="does not match adapter's bound tenant"):
        asyncio.run(
            adapter.insert_or_skip(
                tenant_context=foreign_context,
                user_id="operator-001",
                trigger_type="daily_scheduled",
                idempotency_key="2026-05-28",
            )
        )
