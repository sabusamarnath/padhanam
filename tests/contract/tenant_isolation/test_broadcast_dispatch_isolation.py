"""Tenant isolation contract for BroadcastDispatch (D24, D143, S53).

The BroadcastDispatch substrate is in-process at Phase 2-A; it carries
no persistence and no tenant-scoped session. Tenant isolation at the
dispatch boundary is the contract that the ``tenant_id`` the caller
passes to ``dispatch`` is the exact ``tenant_id`` the registered
BroadcastFlow implementer receives at ``fire`` — no rewriting, no
cross-tenant bleed, no implicit defaulting.

These scenarios document the structural invariant and pin it via
adapter behaviour. When a Phase 2-B+ swap introduces an out-of-process
queue adapter, this scenario carries forward unchanged: the queued
trigger context still carries the ``tenant_id`` the caller passed.

D24 requires every adapter touching tenant-scoped data to ship with
tenant_isolation contract scenarios. The dispatch port touches
tenant-scoped *invocation* rather than tenant-scoped data; the
contract still belongs here so the audit surface includes the
dispatch behaviour.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from contexts.messaging.adapters.dispatch.in_process_broadcast_dispatch_adapter import (
    InProcessBroadcastDispatchAdapter,
)
from contexts.messaging.application.ports.broadcast_dispatch import (
    NoRegisteredBroadcastImplementerError,
)
from shared_kernel.broadcast_flow import (
    BroadcastResponse,
    BroadcastTriggerType,
    TriggerContext,
)
from shared_kernel.conversation_flow import ArtefactCitation


@dataclass(frozen=True)
class _StubResponse:
    cited_intake_records: tuple[UUID, ...]
    cited_audit_events: tuple[UUID, ...]
    cited_artefacts: tuple[ArtefactCitation, ...]


class _RecordingImplementer:
    def __init__(self) -> None:
        self.recorded_tenant_ids: list[UUID] = []
        self.recorded_user_ids: list[str] = []

    async def fire(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        trigger_context: TriggerContext,
    ) -> BroadcastResponse:
        self.recorded_tenant_ids.append(tenant_id)
        self.recorded_user_ids.append(user_id)
        return _StubResponse(
            cited_intake_records=(),
            cited_audit_events=(),
            cited_artefacts=(),
        )


def _drain_tasks() -> None:
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(0))
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(0))


def test_tenant_id_passes_through_dispatch_to_implementer() -> None:
    """The tenant_id at ``dispatch`` arrives exactly at ``fire``."""
    adapter = InProcessBroadcastDispatchAdapter()
    impl = _RecordingImplementer()
    adapter.register(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED, implementer=impl
    )
    tenant_id = uuid4()

    async def _drive() -> None:
        await adapter.dispatch(
            tenant_id=tenant_id,
            user_id="operator-001",
            trigger_context=TriggerContext(
                trigger_type=BroadcastTriggerType.DAILY_SCHEDULED,
                trigger_id=uuid4(),
                triggered_at="2026-05-27T10:00:00+00:00",
            ),
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    asyncio.run(_drive())
    assert impl.recorded_tenant_ids == [tenant_id]
    assert impl.recorded_user_ids == ["operator-001"]


def test_cross_tenant_dispatches_remain_distinct() -> None:
    """Two tenants' triggers route through the same registered implementer
    with their own tenant_id values; no cross-tenant bleed at the
    dispatch boundary."""
    adapter = InProcessBroadcastDispatchAdapter()
    impl = _RecordingImplementer()
    adapter.register(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED, implementer=impl
    )
    tenant_a = uuid4()
    tenant_b = uuid4()

    async def _drive() -> None:
        await adapter.dispatch(
            tenant_id=tenant_a,
            user_id="op-a",
            trigger_context=TriggerContext(
                trigger_type=BroadcastTriggerType.DAILY_SCHEDULED,
                trigger_id=uuid4(),
                triggered_at="2026-05-27T10:00:00+00:00",
            ),
        )
        await adapter.dispatch(
            tenant_id=tenant_b,
            user_id="op-b",
            trigger_context=TriggerContext(
                trigger_type=BroadcastTriggerType.DAILY_SCHEDULED,
                trigger_id=uuid4(),
                triggered_at="2026-05-27T10:00:01+00:00",
            ),
        )
        # Drain the two spawned tasks.
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    asyncio.run(_drive())
    assert set(impl.recorded_tenant_ids) == {tenant_a, tenant_b}
    assert set(impl.recorded_user_ids) == {"op-a", "op-b"}
    assert len(impl.recorded_tenant_ids) == 2


def test_missing_implementer_failure_is_per_tenant_independent() -> None:
    """A missing implementer error for tenant A does not leak state
    affecting tenant B's subsequent dispatch."""
    adapter = InProcessBroadcastDispatchAdapter()
    impl = _RecordingImplementer()
    adapter.register(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED, implementer=impl
    )
    tenant_a = uuid4()
    tenant_b = uuid4()

    async def _drive_tenant_a() -> None:
        # Tenant A dispatches against a trigger type with no registered
        # implementer; the error surfaces synchronously.
        with pytest.raises(NoRegisteredBroadcastImplementerError):
            await adapter.dispatch(
                tenant_id=tenant_a,
                user_id="op-a",
                trigger_context=TriggerContext(
                    trigger_type=BroadcastTriggerType.MANUAL,
                    trigger_id=uuid4(),
                    triggered_at="2026-05-27T10:00:00+00:00",
                ),
            )

    async def _drive_tenant_b() -> None:
        # Tenant B's subsequent dispatch against the registered type
        # succeeds and reaches the implementer with tenant B's id.
        await adapter.dispatch(
            tenant_id=tenant_b,
            user_id="op-b",
            trigger_context=TriggerContext(
                trigger_type=BroadcastTriggerType.DAILY_SCHEDULED,
                trigger_id=uuid4(),
                triggered_at="2026-05-27T10:00:01+00:00",
            ),
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    asyncio.run(_drive_tenant_a())
    asyncio.run(_drive_tenant_b())
    assert impl.recorded_tenant_ids == [tenant_b]
    assert impl.recorded_user_ids == ["op-b"]
