"""Unit tests for InProcessBroadcastDispatchAdapter (D143, S53).

The adapter is both BroadcastFlowRegistry and BroadcastDispatch. Tests
verify registration mechanics, deterministic routing on trigger_type,
the missing-implementer error path, and structured failure logging on
implementer exceptions.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from contexts.messaging.adapters.dispatch.in_process_broadcast_dispatch_adapter import (
    InProcessBroadcastDispatchAdapter,
)
from contexts.messaging.application.ports.broadcast_dispatch import (
    BroadcastDispatch,
    NoRegisteredBroadcastImplementerError,
)
from contexts.messaging.application.ports.broadcast_flow_registry import (
    BroadcastFlowRegistry,
)
from shared_kernel.broadcast_flow import (
    BroadcastFlow,
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
    """A BroadcastFlow implementer that records every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[UUID, str, TriggerContext]] = []

    async def fire(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        trigger_context: TriggerContext,
    ) -> BroadcastResponse:
        self.calls.append((tenant_id, user_id, trigger_context))
        return _StubResponse(
            cited_intake_records=(),
            cited_audit_events=(),
            cited_artefacts=(),
        )


class _RaisingImplementer:
    """A BroadcastFlow implementer that always raises."""

    def __init__(self) -> None:
        self.calls = 0

    async def fire(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        trigger_context: TriggerContext,
    ) -> BroadcastResponse:
        self.calls += 1
        raise RuntimeError("synthetic implementer failure")


# --------------------------------------------------------------------------- structural typing


def test_adapter_satisfies_dispatch_protocol() -> None:
    adapter = InProcessBroadcastDispatchAdapter()
    assert isinstance(adapter, BroadcastDispatch)


def test_adapter_satisfies_registry_protocol() -> None:
    adapter = InProcessBroadcastDispatchAdapter()
    assert isinstance(adapter, BroadcastFlowRegistry)


# --------------------------------------------------------------------------- registration


def test_registration_records_implementer() -> None:
    adapter = InProcessBroadcastDispatchAdapter()
    impl = _RecordingImplementer()
    adapter.register(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED,
        implementer=impl,
    )
    assert adapter.get(BroadcastTriggerType.DAILY_SCHEDULED) is impl
    assert adapter.registered_types() == frozenset(
        {BroadcastTriggerType.DAILY_SCHEDULED}
    )


def test_registration_is_idempotent_replacing() -> None:
    adapter = InProcessBroadcastDispatchAdapter()
    first = _RecordingImplementer()
    second = _RecordingImplementer()
    adapter.register(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED, implementer=first
    )
    adapter.register(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED, implementer=second
    )
    assert adapter.get(BroadcastTriggerType.DAILY_SCHEDULED) is second


def test_multiple_trigger_types_register_independently() -> None:
    adapter = InProcessBroadcastDispatchAdapter()
    daily = _RecordingImplementer()
    threshold = _RecordingImplementer()
    adapter.register(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED, implementer=daily
    )
    adapter.register(
        trigger_type=BroadcastTriggerType.THRESHOLD_CROSSED,
        implementer=threshold,
    )
    assert adapter.get(BroadcastTriggerType.DAILY_SCHEDULED) is daily
    assert adapter.get(BroadcastTriggerType.THRESHOLD_CROSSED) is threshold
    assert adapter.registered_types() == frozenset(
        {
            BroadcastTriggerType.DAILY_SCHEDULED,
            BroadcastTriggerType.THRESHOLD_CROSSED,
        }
    )


def test_get_returns_none_for_unregistered_trigger() -> None:
    adapter = InProcessBroadcastDispatchAdapter()
    assert adapter.get(BroadcastTriggerType.MANUAL) is None


# --------------------------------------------------------------------------- dispatch


def test_dispatch_routes_to_registered_implementer() -> None:
    adapter = InProcessBroadcastDispatchAdapter()
    impl = _RecordingImplementer()
    adapter.register(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED, implementer=impl
    )
    tenant_id = uuid4()
    trigger_id = uuid4()
    context = TriggerContext(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED,
        trigger_id=trigger_id,
        triggered_at="2026-05-27T10:00:00+00:00",
    )

    async def _drive() -> None:
        await adapter.dispatch(
            tenant_id=tenant_id,
            user_id="operator-001",
            trigger_context=context,
        )
        # Allow the spawned task to complete.
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    asyncio.run(_drive())
    assert len(impl.calls) == 1
    recorded_tenant, recorded_user, recorded_context = impl.calls[0]
    assert recorded_tenant == tenant_id
    assert recorded_user == "operator-001"
    assert recorded_context.trigger_id == trigger_id


def test_dispatch_routes_by_trigger_type() -> None:
    adapter = InProcessBroadcastDispatchAdapter()
    daily = _RecordingImplementer()
    threshold = _RecordingImplementer()
    adapter.register(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED, implementer=daily
    )
    adapter.register(
        trigger_type=BroadcastTriggerType.THRESHOLD_CROSSED,
        implementer=threshold,
    )

    async def _drive() -> None:
        await adapter.dispatch(
            tenant_id=uuid4(),
            user_id="op",
            trigger_context=TriggerContext(
                trigger_type=BroadcastTriggerType.THRESHOLD_CROSSED,
                trigger_id=uuid4(),
                triggered_at="2026-05-27T10:00:00+00:00",
            ),
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    asyncio.run(_drive())
    assert len(daily.calls) == 0
    assert len(threshold.calls) == 1


def test_dispatch_missing_implementer_raises() -> None:
    """A trigger_type with no registered implementer fails fast."""
    adapter = InProcessBroadcastDispatchAdapter()

    async def _drive() -> None:
        with pytest.raises(NoRegisteredBroadcastImplementerError) as exc_info:
            await adapter.dispatch(
                tenant_id=uuid4(),
                user_id="op",
                trigger_context=TriggerContext(
                    trigger_type=BroadcastTriggerType.MANUAL,
                    trigger_id=uuid4(),
                    triggered_at="2026-05-27T10:00:00+00:00",
                ),
            )
        assert exc_info.value.trigger_type == "manual"

    asyncio.run(_drive())


def test_dispatch_logs_implementer_failure_with_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An implementer exception is caught inside the task and logged structurally."""
    adapter = InProcessBroadcastDispatchAdapter()
    impl = _RaisingImplementer()
    adapter.register(
        trigger_type=BroadcastTriggerType.DAILY_SCHEDULED, implementer=impl
    )
    tenant_id = uuid4()
    trigger_id = uuid4()

    async def _drive() -> None:
        await adapter.dispatch(
            tenant_id=tenant_id,
            user_id="operator-001",
            trigger_context=TriggerContext(
                trigger_type=BroadcastTriggerType.DAILY_SCHEDULED,
                trigger_id=trigger_id,
                triggered_at="2026-05-27T10:00:00+00:00",
            ),
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    with caplog.at_level(logging.ERROR, logger="padhanam.messaging.broadcast_dispatch"):
        asyncio.run(_drive())
    assert impl.calls == 1
    # Implementer failure logged structurally.
    assert any(
        "broadcast implementer fire failed" in record.message
        for record in caplog.records
    )
    # The structured context carries identifying tags.
    failure_records = [
        r
        for r in caplog.records
        if "broadcast implementer fire failed" in r.message
    ]
    assert failure_records
    context_dict = getattr(failure_records[0], "context", {})
    assert context_dict.get("trigger_id") == str(trigger_id)
    assert context_dict.get("trigger_type") == "daily_scheduled"
    assert context_dict.get("tenant_id") == str(tenant_id)
    assert context_dict.get("user_id") == "operator-001"


def test_dispatch_context_kwarg_extends_log_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Caller-supplied ``context`` dict merges into the failure log context."""
    adapter = InProcessBroadcastDispatchAdapter()
    impl = _RaisingImplementer()
    adapter.register(
        trigger_type=BroadcastTriggerType.MANUAL, implementer=impl
    )

    async def _drive() -> None:
        await adapter.dispatch(
            tenant_id=uuid4(),
            user_id="op",
            trigger_context=TriggerContext(
                trigger_type=BroadcastTriggerType.MANUAL,
                trigger_id=uuid4(),
                triggered_at="2026-05-27T10:00:00+00:00",
            ),
            context={"caller": "test"},
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    with caplog.at_level(logging.ERROR, logger="padhanam.messaging.broadcast_dispatch"):
        asyncio.run(_drive())
    failure_records = [
        r
        for r in caplog.records
        if "broadcast implementer fire failed" in r.message
    ]
    assert failure_records
    context_dict = getattr(failure_records[0], "context", {})
    assert context_dict.get("caller") == "test"
