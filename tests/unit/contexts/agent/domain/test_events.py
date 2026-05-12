"""Unit tests for the AgentEvent domain vocabulary (D90, S29b).

The event types are pure-data DTOs at the domain layer; tests cover
construction, frozen semantics, the discriminated-union shape, and the
TERMINAL_EVENT_TYPES helper tuple. Round-trip parsing, JSON encoding,
and SSE wire translation belong to the apps/api adapter tests at
commit 8.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from decimal import Decimal
from typing import get_args
from uuid import UUID

import pytest

from contexts.agent.domain.events import (
    AgentEvent,
    ContentDelta,
    InvariantBlocked,
    InvocationCompleted,
    InvocationFailed,
    InvocationStarted,
    IterationCompleted,
    IterationStarted,
    LLMCallStarted,
    TERMINAL_EVENT_TYPES,
    ToolCallCompleted,
    ToolCallExecuting,
    ToolCallProposed,
)
from contexts.agent.domain.termination import TerminationReason
from shared_kernel import TenantContext


_INVOCATION_ID = UUID("00000000-0000-4000-8000-000000000001")
_AGENT_TEMPLATE_ID = UUID("00000000-0000-4000-8000-000000000002")
_NOW = datetime(2026, 5, 12, 18, 0, 0, tzinfo=timezone.utc)
_TENANT_CONTEXT = TenantContext(
    tenant_id="00000000-0000-4000-8000-0000000000aa",
    jurisdiction="EU",
    cost_attribution_id="alpha",
)


def test_invocation_started_construction() -> None:
    event = InvocationStarted(
        invocation_id=_INVOCATION_ID,
        agent_template_id=_AGENT_TEMPLATE_ID,
        tenant_context=_TENANT_CONTEXT,
        model_name="qwen2.5:7b",
        started_at=_NOW,
    )
    assert event.invocation_id == _INVOCATION_ID
    assert event.agent_template_id == _AGENT_TEMPLATE_ID
    assert event.tenant_context is _TENANT_CONTEXT
    assert event.model_name == "qwen2.5:7b"
    assert event.started_at == _NOW


def test_iteration_started_carries_one_based_index() -> None:
    event = IterationStarted(
        invocation_id=_INVOCATION_ID,
        iteration_index=1,
        started_at=_NOW,
    )
    assert event.iteration_index == 1


def test_llm_call_started_records_message_count() -> None:
    event = LLMCallStarted(
        invocation_id=_INVOCATION_ID,
        iteration_index=1,
        model_name="qwen2.5:7b",
        message_count=3,
        started_at=_NOW,
    )
    assert event.message_count == 3


def test_content_delta_carries_fragment() -> None:
    event = ContentDelta(
        invocation_id=_INVOCATION_ID,
        iteration_index=1,
        text_fragment="Hello",
    )
    assert event.text_fragment == "Hello"


def test_tool_call_proposed_carries_classification_and_arguments() -> None:
    event = ToolCallProposed(
        invocation_id=_INVOCATION_ID,
        iteration_index=2,
        tool_name="retrieval",
        arguments='{"query": "what is LVT"}',
        classification="read_only",
    )
    assert event.tool_name == "retrieval"
    assert event.arguments == '{"query": "what is LVT"}'
    assert event.classification == "read_only"


def test_tool_call_executing_records_started_at() -> None:
    event = ToolCallExecuting(
        invocation_id=_INVOCATION_ID,
        iteration_index=2,
        tool_name="retrieval",
        started_at=_NOW,
    )
    assert event.started_at == _NOW


def test_tool_call_completed_records_success_and_duration() -> None:
    event = ToolCallCompleted(
        invocation_id=_INVOCATION_ID,
        iteration_index=2,
        tool_name="retrieval",
        success=True,
        result_summary="3 chunks retrieved",
        duration_ms=42,
    )
    assert event.success is True
    assert event.duration_ms == 42
    assert event.result_summary == "3 chunks retrieved"


def test_iteration_completed_carries_cost_decimal_and_signal() -> None:
    event = IterationCompleted(
        invocation_id=_INVOCATION_ID,
        iteration_index=1,
        termination_signal="continue",
        duration_ms=1234,
        cost_usd=Decimal("0.00012"),
    )
    assert event.termination_signal == "continue"
    assert event.cost_usd == Decimal("0.00012")
    assert isinstance(event.cost_usd, Decimal)


def test_invocation_completed_carries_termination_reason_and_audit_pair() -> None:
    event = InvocationCompleted(
        invocation_id=_INVOCATION_ID,
        final_result="Here is the framing.",
        termination_reason=TerminationReason.CONTENT,
        total_cost_usd=Decimal("0.00045"),
        audit_chain_hashes=("a" * 64, "b" * 64),
        duration_ms=5500,
    )
    assert event.termination_reason is TerminationReason.CONTENT
    assert event.audit_chain_hashes == ("a" * 64, "b" * 64)


def test_invocation_failed_carries_variable_length_partial_chain() -> None:
    # Pre-start failure: zero hashes.
    event = InvocationFailed(
        invocation_id=_INVOCATION_ID,
        error_type="RuntimeError",
        error_detail="boom",
        partial_audit_chain_state=(),
        duration_ms=10,
    )
    assert event.partial_audit_chain_state == ()

    # Post-start, pre-end failure: one hash.
    event_with_start = dataclasses.replace(
        event, partial_audit_chain_state=("a" * 64,)
    )
    assert event_with_start.partial_audit_chain_state == ("a" * 64,)

    # Post-end failure: two hashes (rare but valid).
    event_with_both = dataclasses.replace(
        event, partial_audit_chain_state=("a" * 64, "b" * 64)
    )
    assert event_with_both.partial_audit_chain_state == ("a" * 64, "b" * 64)


def test_invariant_blocked_records_classification_and_blocked_tool() -> None:
    event = InvariantBlocked(
        invocation_id=_INVOCATION_ID,
        classification="financial",
        blocked_tool_name="stripe_charge",
        audit_chain_hashes=("a" * 64, "b" * 64),
    )
    assert event.classification == "financial"
    assert event.blocked_tool_name == "stripe_charge"
    assert event.audit_chain_hashes == ("a" * 64, "b" * 64)


@pytest.mark.parametrize(
    "event_factory",
    [
        lambda: InvocationStarted(
            invocation_id=_INVOCATION_ID,
            agent_template_id=_AGENT_TEMPLATE_ID,
            tenant_context=_TENANT_CONTEXT,
            model_name="qwen2.5:7b",
            started_at=_NOW,
        ),
        lambda: IterationStarted(
            invocation_id=_INVOCATION_ID,
            iteration_index=1,
            started_at=_NOW,
        ),
        lambda: ContentDelta(
            invocation_id=_INVOCATION_ID,
            iteration_index=1,
            text_fragment="x",
        ),
        lambda: InvocationCompleted(
            invocation_id=_INVOCATION_ID,
            final_result="ok",
            termination_reason=TerminationReason.CONTENT,
            total_cost_usd=Decimal("0"),
            audit_chain_hashes=("a" * 64, "b" * 64),
            duration_ms=1,
        ),
    ],
)
def test_events_are_frozen(event_factory) -> None:
    event = event_factory()
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.invocation_id = UUID(int=0)  # type: ignore[misc]


def test_agent_event_union_lists_all_eleven_types() -> None:
    members = set(get_args(AgentEvent))
    expected = {
        InvocationStarted,
        IterationStarted,
        LLMCallStarted,
        ContentDelta,
        ToolCallProposed,
        ToolCallExecuting,
        ToolCallCompleted,
        IterationCompleted,
        InvocationCompleted,
        InvocationFailed,
        InvariantBlocked,
    }
    assert members == expected
    assert len(members) == 11


def test_terminal_event_types_contains_three_terminators() -> None:
    assert set(TERMINAL_EVENT_TYPES) == {
        InvocationCompleted,
        InvocationFailed,
        InvariantBlocked,
    }


def test_terminal_event_types_distinguishes_terminal_from_intermediate() -> None:
    completed = InvocationCompleted(
        invocation_id=_INVOCATION_ID,
        final_result="ok",
        termination_reason=TerminationReason.CONTENT,
        total_cost_usd=Decimal("0"),
        audit_chain_hashes=("a" * 64, "b" * 64),
        duration_ms=1,
    )
    delta = ContentDelta(
        invocation_id=_INVOCATION_ID,
        iteration_index=1,
        text_fragment="x",
    )
    assert isinstance(completed, TERMINAL_EVENT_TYPES)
    assert not isinstance(delta, TERMINAL_EVENT_TYPES)


def test_termination_reason_re_exports_from_ports_layer() -> None:
    """The relocation at S29b preserves the old import path.

    Existing callers import TerminationReason from
    ``contexts.agent.ports.executor`` and from ``contexts.agent.ports``;
    both paths must continue to resolve to the same class as the new
    domain-layer location.
    """
    from contexts.agent.ports import TerminationReason as ports_via_init
    from contexts.agent.ports.executor import TerminationReason as ports_via_exec

    assert ports_via_init is TerminationReason
    assert ports_via_exec is TerminationReason
