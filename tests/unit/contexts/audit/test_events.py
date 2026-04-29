from __future__ import annotations

import pytest

from contexts.audit.domain.events import (
    GENESIS_HASH,
    AuditEvent,
    compute_event_hash,
    verify_chain,
)


def _make_event(
    *,
    actor: str = "alice",
    tenant_id: str = "tenant-a",
    correlation_id: str = "corr-1",
    previous_event_hash: str = GENESIS_HASH,
    timestamp: str = "2026-04-29T12:00:00+00:00",
    after_state: dict | None = None,
) -> AuditEvent:
    after_state = after_state or {"key": "value"}
    fields = dict(
        actor=actor,
        tenant_id=tenant_id,
        jurisdiction="EU",
        timestamp=timestamp,
        action_verb="create",
        resource_type="tenant_record",
        resource_id="r1",
        before_state={},
        after_state=after_state,
        correlation_id=correlation_id,
        previous_event_hash=previous_event_hash,
    )
    this_hash = compute_event_hash(**fields)
    return AuditEvent(this_event_hash=this_hash, **fields)


def test_chain_round_trip_clean() -> None:
    e1 = _make_event()
    e2 = _make_event(
        previous_event_hash=e1.this_event_hash,
        correlation_id="corr-2",
        timestamp="2026-04-29T12:01:00+00:00",
    )
    e3 = _make_event(
        previous_event_hash=e2.this_event_hash,
        correlation_id="corr-3",
        timestamp="2026-04-29T12:02:00+00:00",
    )
    result = verify_chain([e1, e2, e3])
    assert result.is_intact is True
    assert result.break_index is None
    assert result.length == 3


def test_chain_detects_tampered_payload() -> None:
    e1 = _make_event()
    # Tamper with e2's after_state but keep its stored hash unchanged.
    e2_real = _make_event(
        previous_event_hash=e1.this_event_hash,
        correlation_id="corr-2",
        timestamp="2026-04-29T12:01:00+00:00",
    )
    tampered_e2 = AuditEvent(
        actor=e2_real.actor,
        tenant_id=e2_real.tenant_id,
        jurisdiction=e2_real.jurisdiction,
        timestamp=e2_real.timestamp,
        action_verb=e2_real.action_verb,
        resource_type=e2_real.resource_type,
        resource_id=e2_real.resource_id,
        before_state=e2_real.before_state,
        after_state={"key": "tampered"},
        correlation_id=e2_real.correlation_id,
        previous_event_hash=e2_real.previous_event_hash,
        this_event_hash=e2_real.this_event_hash,
    )
    result = verify_chain([e1, tampered_e2])
    assert result.is_intact is False
    assert result.break_index == 1


def test_chain_detects_broken_link() -> None:
    e1 = _make_event()
    # e2 claims a wrong predecessor.
    e2 = _make_event(
        previous_event_hash="ff" * 32,
        correlation_id="corr-2",
        timestamp="2026-04-29T12:01:00+00:00",
    )
    result = verify_chain([e1, e2])
    assert result.is_intact is False
    assert result.break_index == 1


def test_compute_event_hash_is_deterministic() -> None:
    args = dict(
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
    assert compute_event_hash(**args) == compute_event_hash(**args)
