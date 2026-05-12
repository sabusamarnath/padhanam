"""Unit tests for AgentLoopExecutor against the two-thin-ports surface (D89, S28b commit 5).

The executor's surface generalised from the S27b retrieval-as-only-callable
branch to ``ToolInvoker``-driven dispatch. The tool definitions list
arrives pre-resolved on ``EffectiveConstraintBundle.tool_definitions``
(composition resolves it via ``ToolDefinitionsLookup``); the executor
passes that list through to the LiteLLM call and dispatches each
model-issued ``ToolCall`` through ``ToolInvoker``.

The eight scenarios:

1. Content-only response terminates at iteration 1 with CONTENT.
2. Tool call resolved OK terminates after the second LLM turn.
3. Tool call returning INVARIANT_BLOCKED terminates with the new
   ``TerminationReason.INVARIANT_BLOCKED`` and the invariant_index
   on the AgentSignal.
4. Tool call returning TOOL_NOT_REGISTERED terminates with the
   existing ``TerminationReason.TOOL_NOT_REGISTERED`` path.
5. Tool call returning ERROR appends the explanation as a tool-role
   message and continues the loop.
6. Max-iterations cap with continuous tool calls terminates with
   MAX_ITERATIONS.
7. Audit chain integrity holds across the new termination paths.
8. The tool definitions list flows through to the LiteLLM call's
   ``tools`` parameter verbatim.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest

from contexts.agent.adapters.outbound.agent_loop_executor import (
    AgentLoopExecutor,
    MAX_ITERATIONS,
)
from contexts.agent.application.ports import (
    InvocationOutcome,
    ToolInvocationResult,
)
from contexts.agent.domain.effective_bundle import EffectiveConstraintBundle
from contexts.agent.ports.executor import (
    AgentInvocationContext,
    TerminationReason,
)
from contexts.audit.domain.events import (
    AuditEvent,
    GENESIS_HASH,
    compute_event_hash,
)
from contexts.inference.domain.completion import (
    Completion,
    Message,
    TokenUsage,
    ToolCall,
    ToolDefinition,
)
from shared_kernel import TenantContext, ToolAllowlistEntry


_TENANT_A = TenantContext(
    tenant_id="00000000-0000-4000-8000-00000000a001",
    jurisdiction="eu-west",
    cost_attribution_id="00000000-0000-4000-8000-00000000a001",
)

_RETRIEVAL_ENTRY = ToolAllowlistEntry(
    tool_id=UUID("00000000-0000-0000-0000-000000000001"),
    revision_id=UUID("00000000-0000-0000-0000-000000000002"),
)

_RETRIEVAL_DEFINITION = ToolDefinition(
    name="retrieval",
    description="Search.",
    parameters={"type": "object", "properties": {"query": {"type": "string"}}},
)


def _bundle() -> EffectiveConstraintBundle:
    return EffectiveConstraintBundle(
        system_prompt="be helpful",
        tool_allowlist=(_RETRIEVAL_ENTRY,),
        retrieval_strategy={"primary": "vector"},
        filter_tree={},
        top_k=5,
        min_score=Decimal("0.5"),
        model_selection="qwen2.5:7b",
    )


def _context(
    *,
    tool_definitions: tuple[ToolDefinition, ...] = (_RETRIEVAL_DEFINITION,),
    methodology_id: UUID | None = None,
) -> AgentInvocationContext:
    return AgentInvocationContext(
        tenant_context=_TENANT_A,
        agent_template_id=uuid4(),
        agent_revision_version=1,
        role_template_id=uuid4(),
        role_revision_version=1,
        methodology_template_id=methodology_id,
        methodology_version=1 if methodology_id else None,
        effective_bundle=_bundle(),
        user_input="help me frame this problem",
        tool_definitions=tool_definitions,
    )


def _completion(
    *,
    text: str = "",
    tool_calls: tuple[ToolCall, ...] = (),
    cost: str = "0",
) -> Completion:
    return Completion(
        text=text,
        model="qwen2.5:7b",
        usage=TokenUsage(input_tokens=10, output_tokens=4),
        tool_calls=tool_calls,
        cost_usd=Decimal(cost),
    )


class _ScriptedInferencePort:
    def __init__(self, completions: list[Completion]) -> None:
        self._completions = list(completions)
        self.calls: list[
            tuple[Sequence[Message], str | None, TenantContext, Sequence[ToolDefinition]]
        ] = []

    def complete(
        self,
        messages: Sequence[Message],
        model: str | None,
        tenant_context: TenantContext,
        tools: Sequence[ToolDefinition] = (),
    ) -> Completion:
        self.calls.append(
            (list(messages), model, tenant_context, list(tools))
        )
        if not self._completions:
            raise AssertionError("ScriptedInferencePort exhausted")
        return self._completions.pop(0)


class _ScriptedToolInvoker:
    """Replays a queue of pre-canned ToolInvocationResults."""

    def __init__(self, results: list[ToolInvocationResult]) -> None:
        self._results = list(results)
        self.calls: list[dict[str, Any]] = []

    async def __call__(
        self,
        *,
        tool_call: ToolCall,
        tenant_context: TenantContext,
    ) -> ToolInvocationResult:
        self.calls.append(
            {"tool_call": tool_call, "tenant_context": tenant_context}
        )
        if not self._results:
            raise AssertionError("ScriptedToolInvoker exhausted")
        return self._results.pop(0)


class _ChainingFakeAuditPort:
    def __init__(self) -> None:
        self.chains: dict[str, list[AuditEvent]] = {}

    async def emit(self, event: AuditEvent) -> AuditEvent:
        chain = self.chains.setdefault(event.tenant_id, [])
        previous = chain[-1].this_event_hash if chain else GENESIS_HASH
        this_hash = compute_event_hash(
            actor=event.actor,
            tenant_id=event.tenant_id,
            jurisdiction=event.jurisdiction,
            timestamp=event.timestamp,
            action_verb=event.action_verb,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            before_state=event.before_state,
            after_state=event.after_state,
            correlation_id=event.correlation_id,
            previous_event_hash=previous,
        )
        persisted = AuditEvent(
            actor=event.actor,
            tenant_id=event.tenant_id,
            jurisdiction=event.jurisdiction,
            timestamp=event.timestamp,
            action_verb=event.action_verb,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            before_state=event.before_state,
            after_state=event.after_state,
            correlation_id=event.correlation_id,
            previous_event_hash=previous,
            this_event_hash=this_hash,
        )
        chain.append(persisted)
        return persisted


def _executor(
    *,
    inference: _ScriptedInferencePort,
    invoker: _ScriptedToolInvoker,
    audit: _ChainingFakeAuditPort,
) -> AgentLoopExecutor:
    return AgentLoopExecutor(
        inference_port=inference,
        tool_invoker=invoker,
        audit_port=audit,
    )


# 1. Content-only termination.

def test_content_only_response_terminates_at_iteration_one() -> None:
    inference = _ScriptedInferencePort(
        [_completion(text="here is your framed problem", cost="0.001")]
    )
    invoker = _ScriptedToolInvoker([])
    audit = _ChainingFakeAuditPort()
    executor = _executor(inference=inference, invoker=invoker, audit=audit)

    result = asyncio.run(executor.execute(_context()))

    assert result.termination_reason is TerminationReason.CONTENT
    assert result.iteration_count == 1
    assert result.response_content == "here is your framed problem"
    assert invoker.calls == []


# 2. Tool call resolved OK then content.

def test_tool_call_ok_then_content() -> None:
    inference = _ScriptedInferencePort(
        [
            _completion(
                tool_calls=(
                    ToolCall(id="c1", name="retrieval", arguments_json='{"query": "scope"}'),
                ),
                cost="0.001",
            ),
            _completion(text="final answer", cost="0.002"),
        ]
    )
    invoker = _ScriptedToolInvoker(
        [
            ToolInvocationResult(
                outcome=InvocationOutcome.OK,
                payload="[score=0.9] relevant chunk",
            )
        ]
    )
    audit = _ChainingFakeAuditPort()
    executor = _executor(inference=inference, invoker=invoker, audit=audit)

    result = asyncio.run(executor.execute(_context()))

    assert result.termination_reason is TerminationReason.CONTENT
    assert result.iteration_count == 2
    assert result.response_content == "final answer"
    assert len(invoker.calls) == 1
    assert invoker.calls[0]["tool_call"].name == "retrieval"
    # Second LLM call sees the tool-role message in the conversation.
    second_call_msgs = inference.calls[1][0]
    assert any(m.role == "tool" and "relevant chunk" in m.content for m in second_call_msgs)


# 3. INVARIANT_BLOCKED termination path.

def test_invariant_blocked_terminates_with_invariant_signal() -> None:
    inference = _ScriptedInferencePort(
        [
            _completion(
                tool_calls=(
                    ToolCall(
                        id="c1",
                        name="transfer",
                        arguments_json='{"amount": 1000}',
                    ),
                ),
                cost="0.001",
            )
        ]
    )
    invoker = _ScriptedToolInvoker(
        [
            ToolInvocationResult(
                outcome=InvocationOutcome.INVARIANT_BLOCKED,
                payload="(invocation blocked by invariant 1)",
                message=(
                    "tool 'transfer' is gated by platform invariant 1; "
                    "invocation prohibited at Phase 1"
                ),
                invariant_index=1,
            )
        ]
    )
    audit = _ChainingFakeAuditPort()
    executor = _executor(inference=inference, invoker=invoker, audit=audit)

    result = asyncio.run(executor.execute(_context()))

    assert result.termination_reason is TerminationReason.INVARIANT_BLOCKED
    assert result.early_termination is True
    assert any(
        s.kind == "invariant_blocked"
        and s.payload.get("invariant_index") == 1
        and s.payload.get("tool_name") == "transfer"
        for s in result.signals
    )


# 4. TOOL_NOT_REGISTERED termination path.

def test_tool_not_registered_terminates() -> None:
    inference = _ScriptedInferencePort(
        [
            _completion(
                tool_calls=(
                    ToolCall(id="c1", name="unknown_tool", arguments_json="{}"),
                ),
                cost="0.001",
            )
        ]
    )
    invoker = _ScriptedToolInvoker(
        [
            ToolInvocationResult(
                outcome=InvocationOutcome.TOOL_NOT_REGISTERED,
                payload="(tool not registered)",
                message="tool 'unknown_tool' not in registry",
            )
        ]
    )
    audit = _ChainingFakeAuditPort()
    executor = _executor(inference=inference, invoker=invoker, audit=audit)

    result = asyncio.run(executor.execute(_context()))

    assert result.termination_reason is TerminationReason.TOOL_NOT_REGISTERED
    assert result.early_termination is True


# 5. ERROR outcome continues the loop.

def test_tool_error_continues_loop_with_error_payload() -> None:
    inference = _ScriptedInferencePort(
        [
            _completion(
                tool_calls=(
                    ToolCall(id="c1", name="retrieval", arguments_json='{"query": "x"}'),
                ),
                cost="0.001",
            ),
            _completion(text="recovered after error", cost="0.001"),
        ]
    )
    invoker = _ScriptedToolInvoker(
        [
            ToolInvocationResult(
                outcome=InvocationOutcome.ERROR,
                payload="(retrieval failed: backend unavailable)",
                message="retrieval failed",
            )
        ]
    )
    audit = _ChainingFakeAuditPort()
    executor = _executor(inference=inference, invoker=invoker, audit=audit)

    result = asyncio.run(executor.execute(_context()))

    assert result.termination_reason is TerminationReason.CONTENT
    assert result.iteration_count == 2
    # Error payload reaches the LLM as a tool-role message.
    second_call_msgs = inference.calls[1][0]
    assert any(
        m.role == "tool" and "retrieval failed" in m.content
        for m in second_call_msgs
    )


# 6. Max iterations cap.

def test_max_iterations_cap_terminates_with_max_iterations() -> None:
    completions = []
    for _ in range(MAX_ITERATIONS):
        completions.append(
            _completion(
                tool_calls=(
                    ToolCall(id=f"c{_}", name="retrieval", arguments_json='{"query": "x"}'),
                ),
                cost="0.001",
            )
        )
    invoker_results = [
        ToolInvocationResult(outcome=InvocationOutcome.OK, payload="result")
        for _ in range(MAX_ITERATIONS)
    ]
    inference = _ScriptedInferencePort(completions)
    invoker = _ScriptedToolInvoker(invoker_results)
    audit = _ChainingFakeAuditPort()
    executor = _executor(inference=inference, invoker=invoker, audit=audit)

    result = asyncio.run(executor.execute(_context()))

    assert result.termination_reason is TerminationReason.MAX_ITERATIONS
    assert result.iteration_count == MAX_ITERATIONS


# 7. Tool definitions flow through to LiteLLM verbatim.

def test_tool_definitions_pass_through_to_inference_call() -> None:
    custom_def = ToolDefinition(
        name="search",
        description="search the web",
        parameters={"type": "object"},
    )
    inference = _ScriptedInferencePort(
        [_completion(text="done", cost="0")]
    )
    invoker = _ScriptedToolInvoker([])
    audit = _ChainingFakeAuditPort()
    executor = _executor(inference=inference, invoker=invoker, audit=audit)

    ctx = _context(tool_definitions=(custom_def,))
    asyncio.run(executor.execute(ctx))

    sent_tools = inference.calls[0][3]
    assert sent_tools == [custom_def]


def test_empty_tool_definitions_means_loop_calls_llm_without_tools() -> None:
    inference = _ScriptedInferencePort(
        [_completion(text="content", cost="0")]
    )
    invoker = _ScriptedToolInvoker([])
    audit = _ChainingFakeAuditPort()
    executor = _executor(inference=inference, invoker=invoker, audit=audit)

    ctx = _context(tool_definitions=())
    asyncio.run(executor.execute(ctx))

    sent_tools = inference.calls[0][3]
    assert sent_tools == []


# 8. Audit chain integrity across the new termination paths.

def test_audit_chain_integrity_through_invariant_blocked_path() -> None:
    inference = _ScriptedInferencePort(
        [
            _completion(
                tool_calls=(
                    ToolCall(id="c1", name="transfer", arguments_json="{}"),
                ),
                cost="0.001",
            )
        ]
    )
    invoker = _ScriptedToolInvoker(
        [
            ToolInvocationResult(
                outcome=InvocationOutcome.INVARIANT_BLOCKED,
                payload="blocked",
                message="msg",
                invariant_index=2,
            )
        ]
    )
    audit = _ChainingFakeAuditPort()
    executor = _executor(inference=inference, invoker=invoker, audit=audit)

    result = asyncio.run(executor.execute(_context()))

    chain = audit.chains[_TENANT_A.tenant_id]
    assert len(chain) == 2
    assert chain[0].previous_event_hash == GENESIS_HASH
    assert chain[1].previous_event_hash == chain[0].this_event_hash
    assert chain[1].after_state["termination_reason"] == "invariant_blocked"
    assert result.audit_start_hash == chain[0].this_event_hash
    assert result.audit_end_hash == chain[1].this_event_hash
