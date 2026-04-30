from __future__ import annotations

import asyncio
import logging

import pytest

from contexts.audit.adapters.outbound.noop import NoOpAuditAdapter
from contexts.audit.domain.events import GENESIS_HASH, AuditEvent, compute_event_hash
from shared_kernel import TenantId


def _event() -> AuditEvent:
    fields = dict(
        actor="alice",
        tenant_id="tenant-a",
        jurisdiction="EU",
        timestamp="2026-04-29T12:00:00+00:00",
        action_verb="create",
        resource_type="tenant_record",
        resource_id="r1",
        before_state={},
        after_state={"key": "value"},
        correlation_id="corr-1",
        previous_event_hash=GENESIS_HASH,
    )
    return AuditEvent(this_event_hash=compute_event_hash(**fields), **fields)


def test_emit_does_not_raise(caplog: pytest.LogCaptureFixture) -> None:
    adapter = NoOpAuditAdapter()
    with caplog.at_level(logging.INFO, logger="contexts.audit.noop"):
        asyncio.run(adapter.emit(_event()))
    assert any("audit_event" in record.message for record in caplog.records)


def test_verify_chain_raises_not_implemented() -> None:
    adapter = NoOpAuditAdapter()
    with pytest.raises(NotImplementedError, match="P3"):
        asyncio.run(adapter.verify_chain(TenantId("tenant-a")))
