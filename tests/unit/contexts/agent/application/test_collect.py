"""Unit tests for collect_to_result helper (D90, S29b).

The helper bridges the canonical AgentEvent stream surface to the
legacy synchronous AgentResult shape. Tests cover the three terminal-
event paths (InvocationCompleted, InvariantBlocked, InvocationFailed),
the content-delta accumulation, the iteration-count tracking, and the
structural-error path (stream ends without a terminal event).

Async tests follow the project convention of driving via
``asyncio.run`` per ``tests/unit/contexts/agent/application/test_invoke_agent.py``
rather than pytest-asyncio.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import AsyncIterator
from uuid import UUID

import pytest

from contexts.agent.application.collect import (
    EventStreamEndedWithoutTerminalError,
    collect_to_result,
)
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


async def _stream(events: list[AgentEvent]) -> AsyncIterator[AgentEvent]:
    for e in events:
        yield e


def test_happy_path_yields_clean_agent_result() -> None:
    events: list[AgentEvent] = [
        InvocationStarted(
            invocation_id=_INVOCATION_ID,
            agent_template_id=_AGENT_TEMPLATE_ID,
            tenant_context=_TENANT_CONTEXT,
            model_name="qwen2.5:7b",
            started_at=_NOW,
        ),
        IterationStarted(
            invocation_id=_INVOCATION_ID,
            iteration_index=1,
            started_at=_NOW,
        ),
        LLMCallStarted(
            invocation_id=_INVOCATION_ID,
            iteration_index=1,
            model_name="qwen2.5:7b",
            message_count=2,
            started_at=_NOW,
        ),
        ContentDelta(
            invocation_id=_INVOCATION_ID, iteration_index=1, text_fragment="Hello "
        ),
        ContentDelta(
            invocation_id=_INVOCATION_ID, iteration_index=1, text_fragment="world"
        ),
        IterationCompleted(
            invocation_id=_INVOCATION_ID,
            iteration_index=1,
            termination_signal="content",
            duration_ms=1234,
            cost_usd=Decimal("0.00012"),
        ),
        InvocationCompleted(
            invocation_id=_INVOCATION_ID,
            final_result="Hello world",
            termination_reason=TerminationReason.CONTENT,
            total_cost_usd=Decimal("0.00012"),
            audit_chain_hashes=("a" * 64, "b" * 64),
            duration_ms=2500,
        ),
    ]
    result = asyncio.run(collect_to_result(_stream(events)))

    assert result.response_content == "Hello world"
    assert result.cost_total_usd == Decimal("0.00012")
    assert result.iteration_count == 1
    assert result.termination_reason is TerminationReason.CONTENT
    assert result.audit_start_hash == "a" * 64
    assert result.audit_end_hash == "b" * 64
    assert result.early_termination is False
    assert result.signals == ()


def test_invariant_blocked_path_yields_invariant_blocked_result() -> None:
    events: list[AgentEvent] = [
        InvocationStarted(
            invocation_id=_INVOCATION_ID,
            agent_template_id=_AGENT_TEMPLATE_ID,
            tenant_context=_TENANT_CONTEXT,
            model_name="qwen2.5:7b",
            started_at=_NOW,
        ),
        IterationStarted(
            invocation_id=_INVOCATION_ID,
            iteration_index=1,
            started_at=_NOW,
        ),
        ToolCallProposed(
            invocation_id=_INVOCATION_ID,
            iteration_index=1,
            tool_name="stripe_charge",
            arguments='{"amount": 100}',
            classification="financial",
        ),
        InvariantBlocked(
            invocation_id=_INVOCATION_ID,
            classification="financial",
            blocked_tool_name="stripe_charge",
            audit_chain_hashes=("a" * 64, "b" * 64),
        ),
    ]
    result = asyncio.run(collect_to_result(_stream(events)))

    assert result.termination_reason is TerminationReason.INVARIANT_BLOCKED
    assert result.early_termination is True
    assert result.audit_start_hash == "a" * 64
    assert result.audit_end_hash == "b" * 64


def test_invocation_failed_path_with_no_partial_audit_state() -> None:
    """Pre-start failure: partial_audit_chain_state is empty."""
    events: list[AgentEvent] = [
        InvocationFailed(
            invocation_id=_INVOCATION_ID,
            error_type="RuntimeError",
            error_detail="boom",
            partial_audit_chain_state=(),
            duration_ms=10,
        ),
    ]
    result = asyncio.run(collect_to_result(_stream(events)))

    assert result.termination_reason is TerminationReason.ERROR
    assert result.audit_start_hash == ""
    assert result.audit_end_hash == ""
    assert result.early_termination is True


def test_invocation_failed_path_with_start_hash_only() -> None:
    """Post-start, pre-end failure: one hash populated."""
    events: list[AgentEvent] = [
        InvocationStarted(
            invocation_id=_INVOCATION_ID,
            agent_template_id=_AGENT_TEMPLATE_ID,
            tenant_context=_TENANT_CONTEXT,
            model_name="qwen2.5:7b",
            started_at=_NOW,
        ),
        InvocationFailed(
            invocation_id=_INVOCATION_ID,
            error_type="TimeoutError",
            error_detail="timed out after 30s",
            partial_audit_chain_state=("a" * 64,),
            duration_ms=30000,
        ),
    ]
    result = asyncio.run(collect_to_result(_stream(events)))

    assert result.termination_reason is TerminationReason.ERROR
    assert result.audit_start_hash == "a" * 64
    assert result.audit_end_hash == ""


def test_content_deltas_accumulate_through_failure_path() -> None:
    """Non-clean termination should surface accumulated content."""
    events: list[AgentEvent] = [
        IterationStarted(
            invocation_id=_INVOCATION_ID,
            iteration_index=1,
            started_at=_NOW,
        ),
        ContentDelta(
            invocation_id=_INVOCATION_ID, iteration_index=1, text_fragment="partial "
        ),
        ContentDelta(
            invocation_id=_INVOCATION_ID, iteration_index=1, text_fragment="content"
        ),
        InvocationFailed(
            invocation_id=_INVOCATION_ID,
            error_type="RuntimeError",
            error_detail="interrupted",
            partial_audit_chain_state=("a" * 64,),
            duration_ms=100,
        ),
    ]
    result = asyncio.run(collect_to_result(_stream(events)))
    assert result.response_content == "partial content"


def test_iteration_count_tracks_highest_started_index() -> None:
    events: list[AgentEvent] = [
        IterationStarted(
            invocation_id=_INVOCATION_ID,
            iteration_index=1,
            started_at=_NOW,
        ),
        IterationCompleted(
            invocation_id=_INVOCATION_ID,
            iteration_index=1,
            termination_signal="continue",
            duration_ms=100,
            cost_usd=Decimal("0.0001"),
        ),
        IterationStarted(
            invocation_id=_INVOCATION_ID,
            iteration_index=2,
            started_at=_NOW,
        ),
        IterationCompleted(
            invocation_id=_INVOCATION_ID,
            iteration_index=2,
            termination_signal="continue",
            duration_ms=100,
            cost_usd=Decimal("0.0001"),
        ),
        IterationStarted(
            invocation_id=_INVOCATION_ID,
            iteration_index=3,
            started_at=_NOW,
        ),
        InvocationCompleted(
            invocation_id=_INVOCATION_ID,
            final_result="done",
            termination_reason=TerminationReason.CONTENT,
            total_cost_usd=Decimal("0.0003"),
            audit_chain_hashes=("a" * 64, "b" * 64),
            duration_ms=300,
        ),
    ]
    result = asyncio.run(collect_to_result(_stream(events)))
    assert result.iteration_count == 3


def test_stream_without_terminal_event_raises_structural_error() -> None:
    events: list[AgentEvent] = [
        IterationStarted(
            invocation_id=_INVOCATION_ID,
            iteration_index=1,
            started_at=_NOW,
        ),
        ContentDelta(
            invocation_id=_INVOCATION_ID, iteration_index=1, text_fragment="hello"
        ),
    ]
    with pytest.raises(EventStreamEndedWithoutTerminalError):
        asyncio.run(collect_to_result(_stream(events)))


def test_intermediate_tool_events_are_discarded() -> None:
    """ToolCallProposed/Executing/Completed in the stream don't surface
    on AgentResult; collect_to_result discards them."""
    events: list[AgentEvent] = [
        IterationStarted(
            invocation_id=_INVOCATION_ID, iteration_index=1, started_at=_NOW
        ),
        ToolCallProposed(
            invocation_id=_INVOCATION_ID,
            iteration_index=1,
            tool_name="retrieval",
            arguments='{"query": "x"}',
            classification="read_only",
        ),
        ToolCallExecuting(
            invocation_id=_INVOCATION_ID,
            iteration_index=1,
            tool_name="retrieval",
            started_at=_NOW,
        ),
        ToolCallCompleted(
            invocation_id=_INVOCATION_ID,
            iteration_index=1,
            tool_name="retrieval",
            success=True,
            result_summary="3 chunks",
            duration_ms=42,
        ),
        InvocationCompleted(
            invocation_id=_INVOCATION_ID,
            final_result="answered",
            termination_reason=TerminationReason.CONTENT,
            total_cost_usd=Decimal("0.001"),
            audit_chain_hashes=("a" * 64, "b" * 64),
            duration_ms=1500,
        ),
    ]
    result = asyncio.run(collect_to_result(_stream(events)))
    assert result.signals == ()
    assert result.response_content == "answered"
