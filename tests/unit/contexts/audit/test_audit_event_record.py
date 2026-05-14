"""Unit tests for AuditEventRecord construction-time invariants (D102, S36)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contexts.audit.domain.audit_event_record import AuditEventRecord


def _valid_kwargs() -> dict:
    return {
        "id": uuid4(),
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "actor": "user:alice",
        "jurisdiction": "EU-DE",
        "timestamp": datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc),
        "action_verb": "agent.invoke.end",
        "resource_type": "agent_run",
        "resource_id": str(uuid4()),
        "before_state": {},
        "after_state": {"termination_reason": "content"},
        "correlation_id": "corr-abc",
        "previous_event_hash": "0" * 64,
        "this_event_hash": "a" * 64,
    }


def test_valid_record_constructs() -> None:
    record = AuditEventRecord(**_valid_kwargs())
    assert record.actor == "user:alice"
    assert record.jurisdiction == "EU-DE"


def test_control_plane_empty_tenant_id_accepted() -> None:
    kwargs = _valid_kwargs()
    kwargs["tenant_id"] = ""
    record = AuditEventRecord(**kwargs)
    assert record.tenant_id == ""


@pytest.mark.parametrize(
    "field",
    [
        "actor",
        "jurisdiction",
        "action_verb",
        "resource_type",
        "resource_id",
        "correlation_id",
    ],
)
def test_empty_string_on_required_text_field_raises(field: str) -> None:
    kwargs = _valid_kwargs()
    kwargs[field] = ""
    with pytest.raises(ValueError, match=f"AuditEventRecord.{field}"):
        AuditEventRecord(**kwargs)


@pytest.mark.parametrize(
    "hash_field",
    ["previous_event_hash", "this_event_hash"],
)
def test_non_hex_hash_raises(hash_field: str) -> None:
    kwargs = _valid_kwargs()
    kwargs[hash_field] = "z" * 64
    with pytest.raises(ValueError, match=hash_field):
        AuditEventRecord(**kwargs)


@pytest.mark.parametrize(
    "hash_field",
    ["previous_event_hash", "this_event_hash"],
)
def test_short_hash_raises(hash_field: str) -> None:
    kwargs = _valid_kwargs()
    kwargs[hash_field] = "abc"
    with pytest.raises(ValueError, match=hash_field):
        AuditEventRecord(**kwargs)


@pytest.mark.parametrize(
    "hash_field",
    ["previous_event_hash", "this_event_hash"],
)
def test_uppercase_hash_raises(hash_field: str) -> None:
    kwargs = _valid_kwargs()
    kwargs[hash_field] = "A" * 64
    with pytest.raises(ValueError, match=hash_field):
        AuditEventRecord(**kwargs)


def test_frozen() -> None:
    record = AuditEventRecord(**_valid_kwargs())
    with pytest.raises(Exception):
        record.actor = "user:mallory"  # type: ignore[misc]
