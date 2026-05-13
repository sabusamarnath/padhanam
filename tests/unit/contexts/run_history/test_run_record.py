"""Domain unit tests for ``RunRecord`` invariants (D95, S31 commit 2).

Seven invariants land at commit 2; one passing case plus one failing
case per invariant. Plus frozen-dataclass semantics, hex-validation
rejection (length, casing, non-hex characters), parametrized
acceptance of all six ``termination_reason`` values per D95's
reconciliation, and the ``audit_end_hash`` NULL pairing rule
mirroring the schema-layer CHECK
``(termination_reason = 'failed') OR (audit_end_hash IS NOT NULL)``.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from contexts.run_history.domain import RunRecord


_VALID_HASH = "0" * 64
_ALT_HASH = "1" * 64


def _make(**overrides) -> RunRecord:
    """Build a valid ``RunRecord`` with overridable fields.

    The default arguments produce a record that satisfies every
    invariant; tests override one field at a time to exercise a
    specific invariant's failure mode while keeping every other
    field valid.
    """
    defaults = dict(
        id=uuid4(),
        tenant_id="tenant-a",
        jurisdiction="eu-west",
        agent_template_id=uuid4(),
        agent_template_version=1,
        input_message="hello",
        output_content="hi back",
        started_at=datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 5, 13, 12, 1, 0, tzinfo=timezone.utc),
        termination_reason="content",
        iteration_count=1,
        total_cost_usd=Decimal("0.001"),
        trace_id=None,
        audit_start_hash=_VALID_HASH,
        audit_end_hash=_ALT_HASH,
        created_at=datetime(2026, 5, 13, 12, 1, 5, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return RunRecord(**defaults)


# --- Happy path ---


def test_valid_record_constructs() -> None:
    record = _make()
    assert record.tenant_id == "tenant-a"
    assert record.termination_reason == "content"
    assert record.audit_end_hash == _ALT_HASH


# --- Invariant 1: tenant_id non-empty ---


def test_tenant_id_must_be_non_empty() -> None:
    with pytest.raises(ValueError, match="tenant_id"):
        _make(tenant_id="")


# --- Invariant 2: jurisdiction non-empty ---


def test_jurisdiction_must_be_non_empty() -> None:
    with pytest.raises(ValueError, match="jurisdiction"):
        _make(jurisdiction="")


# --- Invariant 3: iteration_count >= 0 ---


def test_iteration_count_must_be_non_negative() -> None:
    with pytest.raises(ValueError, match="iteration_count"):
        _make(iteration_count=-1)


def test_iteration_count_zero_is_valid() -> None:
    record = _make(iteration_count=0)
    assert record.iteration_count == 0


# --- Invariant 4: total_cost_usd >= 0 ---


def test_total_cost_usd_must_be_non_negative() -> None:
    with pytest.raises(ValueError, match="total_cost_usd"):
        _make(total_cost_usd=Decimal("-0.01"))


def test_total_cost_usd_zero_is_valid() -> None:
    record = _make(total_cost_usd=Decimal("0"))
    assert record.total_cost_usd == Decimal("0")


# --- Invariant 5: hash fields are 64 lowercase hex chars ---


def test_audit_start_hash_rejects_short_string() -> None:
    with pytest.raises(ValueError, match="audit_start_hash"):
        _make(audit_start_hash="abc")


def test_audit_start_hash_rejects_non_hex_characters() -> None:
    bad = "g" * 64
    with pytest.raises(ValueError, match="audit_start_hash"):
        _make(audit_start_hash=bad)


def test_audit_start_hash_rejects_uppercase() -> None:
    bad = "A" * 64
    with pytest.raises(ValueError, match="audit_start_hash"):
        _make(audit_start_hash=bad)


def test_audit_end_hash_rejects_short_string() -> None:
    with pytest.raises(ValueError, match="audit_end_hash"):
        _make(audit_end_hash="too short")


def test_audit_end_hash_rejects_non_hex_characters() -> None:
    bad = "g" * 64
    with pytest.raises(ValueError, match="audit_end_hash"):
        _make(audit_end_hash=bad)


# --- Invariant 6: completed_at >= started_at ---


def test_completed_at_must_not_precede_started_at() -> None:
    start = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 13, 11, 59, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="completed_at"):
        _make(started_at=start, completed_at=end)


def test_completed_at_equal_to_started_at_is_valid() -> None:
    t = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)
    record = _make(started_at=t, completed_at=t)
    assert record.completed_at == record.started_at


# --- Invariant 7: termination_reason in six-value set per D95 ---


@pytest.mark.parametrize(
    "reason",
    [
        "content",
        "max_iterations",
        "tool_not_registered",
        "error",
        "invariant_blocked",
        "failed",
    ],
)
def test_all_six_termination_reasons_accepted(reason: str) -> None:
    if reason == "failed":
        record = _make(termination_reason=reason, audit_end_hash=None)
    else:
        record = _make(termination_reason=reason)
    assert record.termination_reason == reason


@pytest.mark.parametrize(
    "bad",
    ["", "tool_loop_complete", "unknown", "FAILED"],
)
def test_termination_reason_rejects_out_of_set_values(bad: str) -> None:
    with pytest.raises(ValueError, match="termination_reason"):
        _make(termination_reason=bad)


# --- audit_end_hash NULL pairing CHECK: only allowed for 'failed' ---


def test_audit_end_hash_null_rejected_for_non_failed_termination() -> None:
    with pytest.raises(ValueError, match="audit_end_hash"):
        _make(termination_reason="content", audit_end_hash=None)


def test_audit_end_hash_can_be_null_when_termination_reason_is_failed() -> None:
    record = _make(termination_reason="failed", audit_end_hash=None)
    assert record.audit_end_hash is None
    assert record.termination_reason == "failed"


def test_audit_end_hash_can_be_present_when_termination_reason_is_failed() -> None:
    record = _make(termination_reason="failed", audit_end_hash=_ALT_HASH)
    assert record.audit_end_hash == _ALT_HASH


# --- Frozen-dataclass semantics ---


def test_run_record_is_frozen() -> None:
    record = _make()
    with pytest.raises(FrozenInstanceError):
        record.tenant_id = "tenant-b"  # type: ignore[misc]


def test_run_record_equality_is_field_based() -> None:
    record_id = uuid4()
    template_id = uuid4()
    same_args = dict(id=record_id, agent_template_id=template_id)
    record_a = _make(**same_args)
    record_b = _make(**same_args)
    record_c = replace(record_a, tenant_id="tenant-b")
    assert record_a == record_b
    assert record_a != record_c
