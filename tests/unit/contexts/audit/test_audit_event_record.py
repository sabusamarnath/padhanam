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
    ],
)
def test_empty_string_on_required_text_field_raises(field: str) -> None:
    kwargs = _valid_kwargs()
    kwargs[field] = ""
    with pytest.raises(ValueError, match=f"AuditEventRecord.{field}"):
        AuditEventRecord(**kwargs)


def test_empty_correlation_id_accepted_for_engine_internal_events() -> None:
    """Engine-internal events (retrieval_evaluation runner per S40/D110,
    optimization engine per S41/D111) emit audit rows with empty
    correlation_id because they have no inbound HTTP request context.
    Pre-P12 hygiene loosened the validator after S40/S41 rows surfaced
    the cross-context audit semantics drift at the S37 reader's list
    route. The empty-string state is now a legitimate "no inbound HTTP
    context" signal.
    """
    kwargs = _valid_kwargs()
    kwargs["correlation_id"] = ""
    record = AuditEventRecord(**kwargs)
    assert record.correlation_id == ""


def test_non_string_correlation_id_still_raises() -> None:
    """The loosening preserves the type contract — correlation_id must
    still be a string. Numeric or None values raise.
    """
    kwargs = _valid_kwargs()
    kwargs["correlation_id"] = None  # type: ignore[arg-type]
    with pytest.raises(
        ValueError, match="AuditEventRecord.correlation_id must be a string"
    ):
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
