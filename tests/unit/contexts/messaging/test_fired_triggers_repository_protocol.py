"""FiredTriggersRepository Protocol satisfiability tests (D147, S54).

The port is a structural Protocol; both the Postgres adapter and the
in-memory fake must satisfy it. These tests pin the structural-typing
surface so a signature drift on the port breaks a test rather than a
distant call site.
"""

from __future__ import annotations

import asyncio
from typing import get_type_hints

from contexts.messaging.adapters.outbound.postgres.fired_triggers_postgres_adapter import (
    PostgresFiredTriggersAdapter,
)
from contexts.messaging.ports.fired_triggers_repository import (
    FiredTriggersRepository,
)
from shared_kernel import TenantContext, TenantId
from tests.unit.contexts.messaging.application._fakes import (
    FakeFiredTriggersRepository,
)


def test_fake_satisfies_repository_protocol() -> None:
    """The in-memory fake satisfies FiredTriggersRepository structurally."""
    fake: FiredTriggersRepository = FakeFiredTriggersRepository()
    assert hasattr(fake, "insert_or_skip")


def test_postgres_adapter_satisfies_repository_protocol() -> None:
    """The Postgres adapter satisfies FiredTriggersRepository structurally."""

    async def _resolver(_tid: TenantId) -> object:  # noqa: ARG001
        return object()

    adapter: FiredTriggersRepository = PostgresFiredTriggersAdapter(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=TenantId("tenant-a"),
    )
    assert hasattr(adapter, "insert_or_skip")


def test_fake_insert_or_skip_fresh_then_duplicate() -> None:
    """A fresh four-tuple returns True; the same four-tuple returns False."""
    fake = FakeFiredTriggersRepository()
    ctx = TenantContext(
        tenant_id="tenant-a",
        jurisdiction="eu-west",
        cost_attribution_id="tenant-a",
    )

    async def _run() -> tuple[bool, bool]:
        first = await fake.insert_or_skip(
            tenant_context=ctx,
            user_id="operator-001",
            trigger_type="daily_scheduled",
            idempotency_key="2026-05-28",
        )
        second = await fake.insert_or_skip(
            tenant_context=ctx,
            user_id="operator-001",
            trigger_type="daily_scheduled",
            idempotency_key="2026-05-28",
        )
        return first, second

    first, second = asyncio.run(_run())
    assert first is True
    assert second is False


def test_fake_null_idempotency_key_always_fresh() -> None:
    """Null idempotency keys insert fresh each time (Postgres NULL semantics)."""
    fake = FakeFiredTriggersRepository()
    ctx = TenantContext(
        tenant_id="tenant-a",
        jurisdiction="eu-west",
        cost_attribution_id="tenant-a",
    )

    async def _run() -> tuple[bool, bool]:
        first = await fake.insert_or_skip(
            tenant_context=ctx,
            user_id="operator-001",
            trigger_type="manual",
            idempotency_key=None,
        )
        second = await fake.insert_or_skip(
            tenant_context=ctx,
            user_id="operator-001",
            trigger_type="manual",
            idempotency_key=None,
        )
        return first, second

    first, second = asyncio.run(_run())
    assert first is True
    assert second is True
