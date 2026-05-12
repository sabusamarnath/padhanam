"""Unit tests for the AgentExecutor port and its DTOs (D88).

The DTOs are the load-bearing shapes the use case populates and the
adapter consumes. These tests pin construction, frozen invariants,
and the Protocol surface so the executor adapter has a stable target.
"""

from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError
from decimal import Decimal
from typing import get_type_hints
from uuid import UUID, uuid4

import pytest

from contexts.agent.domain.effective_bundle import EffectiveConstraintBundle
from contexts.agent.ports import (
    AgentExecutor,
    AgentInvocationContext,
    AgentResult,
    AgentSignal,
    InvocationMessage,
    TerminationReason,
)
from shared_kernel import TenantContext, ToolAllowlistEntry


_TENANT_A = TenantContext(
    tenant_id="00000000-0000-4000-8000-00000000a001",
    jurisdiction="eu-west",
    cost_attribution_id="00000000-0000-4000-8000-00000000a001",
)
_RETRIEVAL = ToolAllowlistEntry(
    tool_id=UUID("00000000-0000-0000-0000-000000000001"),
    revision_id=UUID("00000000-0000-0000-0000-000000000002"),
)


def _bundle() -> EffectiveConstraintBundle:
    return EffectiveConstraintBundle(
        system_prompt="be helpful",
        tool_allowlist=(_RETRIEVAL,),
        retrieval_strategy={"primary": "vector"},
        filter_tree={},
        top_k=5,
        min_score=Decimal("0.5"),
        model_selection="qwen2.5:7b",
    )


def _invocation_context() -> AgentInvocationContext:
    return AgentInvocationContext(
        tenant_context=_TENANT_A,
        agent_template_id=uuid4(),
        agent_revision_version=1,
        role_template_id=uuid4(),
        role_revision_version=1,
        methodology_template_id=None,
        methodology_version=None,
        effective_bundle=_bundle(),
        user_input="frame this problem for me",
    )


def test_termination_reason_strings_match_audit_payload_shape() -> None:
    assert TerminationReason.CONTENT.value == "content"
    assert TerminationReason.MAX_ITERATIONS.value == "max_iterations"
    assert TerminationReason.TOOL_NOT_REGISTERED.value == "tool_not_registered"
    assert TerminationReason.ERROR.value == "error"
    assert TerminationReason.CONTENT == "content"


def test_invocation_message_is_frozen() -> None:
    m = InvocationMessage(role="user", content="hi")
    with pytest.raises(FrozenInstanceError):
        m.role = "assistant"  # type: ignore[misc]


def test_invocation_context_construction_with_no_methodology() -> None:
    ctx = _invocation_context()
    assert ctx.methodology_template_id is None
    assert ctx.methodology_version is None
    assert ctx.conversation_history == ()
    assert ctx.user_input == "frame this problem for me"


def test_invocation_context_carries_methodology_lineage_when_set() -> None:
    methodology_id = uuid4()
    ctx = AgentInvocationContext(
        tenant_context=_TENANT_A,
        agent_template_id=uuid4(),
        agent_revision_version=1,
        role_template_id=uuid4(),
        role_revision_version=1,
        methodology_template_id=methodology_id,
        methodology_version=3,
        effective_bundle=_bundle(),
        user_input="hi",
    )
    assert ctx.methodology_template_id == methodology_id
    assert ctx.methodology_version == 3


def test_invocation_context_is_frozen() -> None:
    ctx = _invocation_context()
    with pytest.raises(FrozenInstanceError):
        ctx.user_input = "changed"  # type: ignore[misc]


def test_agent_signal_carries_kind_and_payload() -> None:
    sig = AgentSignal(
        kind="retrieval_performed",
        payload={"query": "x", "chunk_count": 3, "top_score": 0.82},
    )
    assert sig.kind == "retrieval_performed"
    assert sig.payload["chunk_count"] == 3


def test_agent_result_construction() -> None:
    r = AgentResult(
        response_content="Here is the framed problem...",
        signals=(),
        cost_total_usd=Decimal("0.001"),
        iteration_count=2,
        termination_reason=TerminationReason.CONTENT,
        audit_start_hash="a" * 64,
        audit_end_hash="b" * 64,
    )
    assert r.response_content.startswith("Here is")
    assert r.iteration_count == 2
    assert r.termination_reason == TerminationReason.CONTENT
    assert r.early_termination is False
    assert r.metadata == {}


def test_agent_result_early_termination_flag() -> None:
    r = AgentResult(
        response_content="(partial)",
        signals=(),
        cost_total_usd=Decimal("0.005"),
        iteration_count=10,
        termination_reason=TerminationReason.MAX_ITERATIONS,
        audit_start_hash="0" * 64,
        audit_end_hash="1" * 64,
        early_termination=True,
    )
    assert r.early_termination is True
    assert r.termination_reason == TerminationReason.MAX_ITERATIONS


def test_agent_result_is_frozen() -> None:
    r = AgentResult(
        response_content="x",
        signals=(),
        cost_total_usd=Decimal("0"),
        iteration_count=1,
        termination_reason=TerminationReason.CONTENT,
        audit_start_hash="0" * 64,
        audit_end_hash="1" * 64,
    )
    with pytest.raises(FrozenInstanceError):
        r.response_content = "different"  # type: ignore[misc]


def test_executor_protocol_has_streaming_execute_method() -> None:
    """Pin the Protocol's single-method shape so adapter implementations
    have an unambiguous target. ``execute`` returns ``AsyncIterator``
    per D90; the method name is preserved (not renamed to ``invoke``)
    per the S29b pre-write reconciliation. The Protocol method is
    declared with ``def`` (not ``async def``) because the adapter's
    implementation is an async generator function — calling such a
    function returns the iterator directly without an extra await.
    """
    methods = {
        name for name in dir(AgentExecutor) if not name.startswith("_")
    }
    assert "execute" in methods
    # Async generator function bodies show as regular (non-coroutine)
    # functions on the class-level descriptor; the iterator-returning
    # shape is reflected via the return type annotation rather than
    # via the coroutine-ness of the function. Verify via the typed
    # return annotation instead of inspect.iscoroutinefunction.
    hints = get_type_hints(AgentExecutor.execute)
    assert "return" in hints
    # Check the typing annotation string mentions AsyncIterator (the
    # actual class identity matches typing.AsyncIterator from the
    # collections.abc registry).
    return_repr = repr(hints["return"])
    assert "AsyncIterator" in return_repr or "AgentEvent" in return_repr
