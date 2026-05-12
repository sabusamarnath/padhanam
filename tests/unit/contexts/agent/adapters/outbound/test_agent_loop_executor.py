"""Unit tests for AgentLoopExecutor — streaming event surface (D88, D89, D90; S29b refactor).

The executor's surface evolved across three sessions:

- S27b (D88): hand-rolled LLM-with-tool-loop returning AgentResult.
- S28b (D89): two-thin-ports refactor (ToolDefinitionsLookup +
  ToolInvoker); ``tool_definitions`` flows on AgentInvocationContext.
- S29b (D90): streaming-only; execute() yields ``AgentEvent`` values.

These tests drive the streaming-aware executor against a scripted
streaming inference port and a scripted tool invoker. Each test
consumes the event stream end-to-end and verifies both:

1. The collect_to_result helper synthesises an AgentResult that
   matches the previous AgentResult shape on the load-bearing fields
   (termination_reason, response_content, iteration_count, audit
   hashes). The legacy ``signals`` field is empty per D90 — the event
   stream is the canonical observability surface.

2. The event stream itself contains the expected event types in the
   expected order with the expected payloads (load-bearing per D90).

The seven scenarios cover the same territory as the S28b test set:

1. Content-only response terminates at iteration 1 with CONTENT.
2. Tool call resolved OK terminates after the second LLM turn.
3. Tool call returning INVARIANT_BLOCKED yields a terminal
   InvariantBlocked event with classification + blocked_tool_name.
4. Tool call returning TOOL_NOT_REGISTERED terminates with the
   existing TerminationReason.TOOL_NOT_REGISTERED path.
5. Tool call returning ERROR appends the explanation as a tool-role
   message and continues the loop.
6. Max-iterations cap with continuous tool calls terminates with
   MAX_ITERATIONS.
7. Audit chain integrity holds across the new termination paths.
8. Tool definitions flow through to the inference call verbatim.
9. (New at S29b) ContentDelta events accumulate from the streaming
   inference port across the loop.
10. (New at S29b) Unhandled exception in the loop yields InvocationFailed
    with the partial audit state.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from decimal import Decimal
from typing import Any, AsyncIterator
from uuid import UUID, uuid4

import pytest

from contexts.agent.adapters.outbound.agent_loop_executor import (
    AgentLoopExecutor,
    MAX_ITERATIONS,
)
from contexts.agent.application.collect import collect_to_result
from contexts.agent.application.ports import (
    InvocationOutcome,
    ToolInvocationResult,
)
from contexts.agent.domain.effective_bundle import EffectiveConstraintBundle
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
    CompletionChunk,
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
    tool_classifications: dict[str, str] | None = None,
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
        tool_classifications=tool_classifications
        or {"retrieval": "read_only"},
    )


def _chunks_for_content(
    text: str, *, cost: str = "0", chunk_count: int = 2
) -> list[CompletionChunk]:
    """Build a streaming chunk list for a content-only completion.

    The text splits into ``chunk_count`` deltas plus a terminal chunk
    carrying the final cost and the empty tool_calls tuple.
    """
    parts: list[str] = []
    if text:
        size = max(1, len(text) // chunk_count)
        for i in range(0, len(text), size):
            parts.append(text[i : i + size])
    chunks = [
        CompletionChunk(text_delta=p, is_final=False) for p in parts
    ]
    chunks.append(
        CompletionChunk(
            text_delta="",
            is_final=True,
            finish_reason="stop",
            model="qwen2.5:7b",
            tool_calls=(),
            usage=TokenUsage(input_tokens=10, output_tokens=len(text)),
            cost_usd=Decimal(cost),
        )
    )
    return chunks


def _chunks_for_tool_calls(
    tool_calls: tuple[ToolCall, ...], *, cost: str = "0", text: str = ""
) -> list[CompletionChunk]:
    """Build a streaming chunk list for a tool-call-issuing completion."""
    chunks: list[CompletionChunk] = []
    if text:
        chunks.append(CompletionChunk(text_delta=text, is_final=False))
    chunks.append(
        CompletionChunk(
            text_delta="",
            is_final=True,
            finish_reason="tool_calls",
            model="qwen2.5:7b",
            tool_calls=tool_calls,
            usage=TokenUsage(input_tokens=10, output_tokens=4),
            cost_usd=Decimal(cost),
        )
    )
    return chunks


class _ScriptedStreamingInferencePort:
    """Replays a queue of pre-canned streaming chunk lists.

    Each list represents one stream_complete invocation. The port
    records each invocation's messages, model, tenant_context, and
    tools for test assertions.
    """

    def __init__(self, completions: list[list[CompletionChunk]]) -> None:
        self._completions = list(completions)
        self.calls: list[
            tuple[
                Sequence[Message],
                str | None,
                TenantContext,
                Sequence[ToolDefinition],
            ]
        ] = []

    def complete(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError(
            "the streaming executor must not call the non-streaming "
            "complete() method; use stream_complete instead"
        )

    async def stream_complete(
        self,
        messages: Sequence[Message],
        model: str | None,
        tenant_context: TenantContext,
        tools: Sequence[ToolDefinition] = (),
    ) -> AsyncIterator[CompletionChunk]:
        self.calls.append(
            (list(messages), model, tenant_context, list(tools))
        )
        if not self._completions:
            raise AssertionError("ScriptedStreamingInferencePort exhausted")
        chunks = self._completions.pop(0)
        for chunk in chunks:
            yield chunk


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
    inference: _ScriptedStreamingInferencePort,
    invoker: _ScriptedToolInvoker,
    audit: _ChainingFakeAuditPort,
) -> AgentLoopExecutor:
    return AgentLoopExecutor(
        inference_port=inference,
        tool_invoker=invoker,
        audit_port=audit,
    )


async def _collect_events(
    executor: AgentLoopExecutor, context: AgentInvocationContext
) -> list[AgentEvent]:
    return [event async for event in executor.execute(context)]


# 1. Content-only termination.

def test_content_only_response_terminates_at_iteration_one() -> None:
    inference = _ScriptedStreamingInferencePort(
        [_chunks_for_content("here is your framed problem", cost="0.001")]
    )
    invoker = _ScriptedToolInvoker([])
    audit = _ChainingFakeAuditPort()
    executor = _executor(inference=inference, invoker=invoker, audit=audit)

    events = asyncio.run(_collect_events(executor, _context()))

    assert isinstance(events[0], InvocationStarted)
    assert isinstance(events[-1], InvocationCompleted)
    terminal = events[-1]
    assert terminal.termination_reason is TerminationReason.CONTENT
    assert terminal.final_result == "here is your framed problem"
    # No tool calls in this path.
    assert invoker.calls == []

    # Sanity-check via collect_to_result.
    result = asyncio.run(
        collect_to_result(
            _replay_events(events)
        )
    )
    assert result.termination_reason is TerminationReason.CONTENT
    assert result.iteration_count == 1
    assert result.response_content == "here is your framed problem"


async def _replay_events(
    events: list[AgentEvent],
) -> AsyncIterator[AgentEvent]:
    for e in events:
        yield e


# 2. Tool call resolved OK then content.

def test_tool_call_ok_then_content() -> None:
    inference = _ScriptedStreamingInferencePort(
        [
            _chunks_for_tool_calls(
                (ToolCall(id="c1", name="retrieval", arguments_json='{"query": "scope"}'),),
                cost="0.001",
            ),
            _chunks_for_content("final answer", cost="0.002"),
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

    events = asyncio.run(_collect_events(executor, _context()))

    terminal = events[-1]
    assert isinstance(terminal, InvocationCompleted)
    assert terminal.termination_reason is TerminationReason.CONTENT
    assert terminal.final_result == "final answer"

    # Verify event ordering: ToolCallProposed → ToolCallExecuting → ToolCallCompleted.
    proposed_idx = next(
        i for i, e in enumerate(events) if isinstance(e, ToolCallProposed)
    )
    executing_idx = next(
        i for i, e in enumerate(events) if isinstance(e, ToolCallExecuting)
    )
    completed_idx = next(
        i for i, e in enumerate(events) if isinstance(e, ToolCallCompleted)
    )
    assert proposed_idx < executing_idx < completed_idx

    completed = events[completed_idx]
    assert completed.success is True
    assert "relevant chunk" in completed.result_summary

    # Second LLM call saw the tool-role message in the conversation.
    second_call_msgs = inference.calls[1][0]
    assert any(
        m.role == "tool" and "relevant chunk" in m.content
        for m in second_call_msgs
    )


# 3. INVARIANT_BLOCKED termination path.

def test_invariant_blocked_yields_terminal_invariant_blocked_event() -> None:
    inference = _ScriptedStreamingInferencePort(
        [
            _chunks_for_tool_calls(
                (
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

    events = asyncio.run(
        _collect_events(
            executor,
            _context(
                tool_classifications={"transfer": "financial"},
            ),
        )
    )

    terminal = events[-1]
    assert isinstance(terminal, InvariantBlocked)
    assert terminal.classification == "financial"
    assert terminal.blocked_tool_name == "transfer"
    assert len(terminal.audit_chain_hashes) == 2

    # ToolCallExecuting and ToolCallCompleted DO NOT fire on the
    # invariant-blocked path (per the executor's intent: the block
    # surfaces before invocation actually runs).
    assert not any(isinstance(e, ToolCallExecuting) for e in events)
    assert not any(isinstance(e, ToolCallCompleted) for e in events)


# 4. TOOL_NOT_REGISTERED termination path.

def test_tool_not_registered_terminates() -> None:
    inference = _ScriptedStreamingInferencePort(
        [
            _chunks_for_tool_calls(
                (ToolCall(id="c1", name="unknown_tool", arguments_json="{}"),),
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

    events = asyncio.run(_collect_events(executor, _context()))

    terminal = events[-1]
    assert isinstance(terminal, InvocationCompleted)
    assert terminal.termination_reason is TerminationReason.TOOL_NOT_REGISTERED


# 5. ERROR outcome continues the loop.

def test_tool_error_continues_loop_with_error_payload() -> None:
    inference = _ScriptedStreamingInferencePort(
        [
            _chunks_for_tool_calls(
                (
                    ToolCall(
                        id="c1",
                        name="retrieval",
                        arguments_json='{"query": "x"}',
                    ),
                ),
                cost="0.001",
            ),
            _chunks_for_content("recovered after error", cost="0.001"),
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

    events = asyncio.run(_collect_events(executor, _context()))

    terminal = events[-1]
    assert isinstance(terminal, InvocationCompleted)
    assert terminal.termination_reason is TerminationReason.CONTENT
    # ToolCallCompleted fires for the ERROR outcome with success=False.
    completed_events = [
        e for e in events if isinstance(e, ToolCallCompleted)
    ]
    assert len(completed_events) == 1
    assert completed_events[0].success is False

    # Error payload reaches the LLM as a tool-role message.
    second_call_msgs = inference.calls[1][0]
    assert any(
        m.role == "tool" and "retrieval failed" in m.content
        for m in second_call_msgs
    )


# 6. Max iterations cap.

def test_max_iterations_cap_terminates_with_max_iterations() -> None:
    completions: list[list[CompletionChunk]] = []
    for i in range(MAX_ITERATIONS):
        completions.append(
            _chunks_for_tool_calls(
                (
                    ToolCall(
                        id=f"c{i}",
                        name="retrieval",
                        arguments_json='{"query": "x"}',
                    ),
                ),
                cost="0.001",
            )
        )
    invoker_results = [
        ToolInvocationResult(outcome=InvocationOutcome.OK, payload="result")
        for _ in range(MAX_ITERATIONS)
    ]
    inference = _ScriptedStreamingInferencePort(completions)
    invoker = _ScriptedToolInvoker(invoker_results)
    audit = _ChainingFakeAuditPort()
    executor = _executor(inference=inference, invoker=invoker, audit=audit)

    events = asyncio.run(_collect_events(executor, _context()))

    terminal = events[-1]
    assert isinstance(terminal, InvocationCompleted)
    assert terminal.termination_reason is TerminationReason.MAX_ITERATIONS

    iteration_started_events = [
        e for e in events if isinstance(e, IterationStarted)
    ]
    assert len(iteration_started_events) == MAX_ITERATIONS


# 7. Audit chain integrity through INVARIANT_BLOCKED path.

def test_audit_chain_integrity_through_invariant_blocked_path() -> None:
    inference = _ScriptedStreamingInferencePort(
        [
            _chunks_for_tool_calls(
                (ToolCall(id="c1", name="transfer", arguments_json="{}"),),
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

    events = asyncio.run(
        _collect_events(
            executor,
            _context(tool_classifications={"transfer": "communication"}),
        )
    )

    chain = audit.chains[_TENANT_A.tenant_id]
    assert len(chain) == 2
    assert chain[0].previous_event_hash == GENESIS_HASH
    assert chain[1].previous_event_hash == chain[0].this_event_hash
    assert chain[1].after_state["termination_reason"] == "invariant_blocked"

    terminal = events[-1]
    assert isinstance(terminal, InvariantBlocked)
    assert terminal.audit_chain_hashes == (
        chain[0].this_event_hash,
        chain[1].this_event_hash,
    )


# 8. Tool definitions flow through to inference call.

def test_tool_definitions_pass_through_to_inference_call() -> None:
    custom_def = ToolDefinition(
        name="search",
        description="search the web",
        parameters={"type": "object"},
    )
    inference = _ScriptedStreamingInferencePort(
        [_chunks_for_content("done", cost="0")]
    )
    invoker = _ScriptedToolInvoker([])
    audit = _ChainingFakeAuditPort()
    executor = _executor(inference=inference, invoker=invoker, audit=audit)

    ctx = _context(tool_definitions=(custom_def,))
    asyncio.run(_collect_events(executor, ctx))

    sent_tools = inference.calls[0][3]
    assert sent_tools == [custom_def]


def test_empty_tool_definitions_means_loop_calls_llm_without_tools() -> None:
    inference = _ScriptedStreamingInferencePort(
        [_chunks_for_content("content", cost="0")]
    )
    invoker = _ScriptedToolInvoker([])
    audit = _ChainingFakeAuditPort()
    executor = _executor(inference=inference, invoker=invoker, audit=audit)

    ctx = _context(tool_definitions=(), tool_classifications={})
    asyncio.run(_collect_events(executor, ctx))

    sent_tools = inference.calls[0][3]
    assert sent_tools == []


# 9. ContentDelta events accumulate from the streaming inference port.

def test_content_deltas_yield_during_streaming() -> None:
    """A multi-chunk content response should yield one ContentDelta event
    per non-empty text delta from the inference adapter."""
    inference = _ScriptedStreamingInferencePort(
        [_chunks_for_content("Hello world", cost="0", chunk_count=4)]
    )
    invoker = _ScriptedToolInvoker([])
    audit = _ChainingFakeAuditPort()
    executor = _executor(inference=inference, invoker=invoker, audit=audit)

    events = asyncio.run(_collect_events(executor, _context()))
    deltas = [e for e in events if isinstance(e, ContentDelta)]
    assert len(deltas) >= 1
    assert "".join(d.text_fragment for d in deltas) == "Hello world"
    terminal = events[-1]
    assert isinstance(terminal, InvocationCompleted)
    assert terminal.final_result == "Hello world"


# 10. Unhandled exception yields InvocationFailed.

def test_unhandled_exception_in_loop_yields_invocation_failed() -> None:
    class _BoomInferencePort:
        async def stream_complete(self, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")
            # unreachable but required for the function to be a generator
            yield  # pragma: no cover

        def complete(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("streaming-only executor calls stream_complete")

    invoker = _ScriptedToolInvoker([])
    audit = _ChainingFakeAuditPort()
    executor = AgentLoopExecutor(
        inference_port=_BoomInferencePort(),  # type: ignore[arg-type]
        tool_invoker=invoker,
        audit_port=audit,
    )

    events = asyncio.run(_collect_events(executor, _context()))

    terminal = events[-1]
    assert isinstance(terminal, InvocationFailed)
    assert terminal.error_type == "RuntimeError"
    assert terminal.error_detail == "boom"
    # Start audit landed before the failure; end audit did not.
    assert len(terminal.partial_audit_chain_state) == 1
    chain = audit.chains[_TENANT_A.tenant_id]
    assert len(chain) == 1
    assert terminal.partial_audit_chain_state[0] == chain[0].this_event_hash


# 11. LLMCallStarted event fires per iteration with message_count.

def test_llm_call_started_event_per_iteration() -> None:
    inference = _ScriptedStreamingInferencePort(
        [
            _chunks_for_tool_calls(
                (
                    ToolCall(
                        id="c1",
                        name="retrieval",
                        arguments_json='{"query": "x"}',
                    ),
                ),
                cost="0.001",
            ),
            _chunks_for_content("done", cost="0.001"),
        ]
    )
    invoker = _ScriptedToolInvoker(
        [
            ToolInvocationResult(
                outcome=InvocationOutcome.OK, payload="result"
            )
        ]
    )
    audit = _ChainingFakeAuditPort()
    executor = _executor(inference=inference, invoker=invoker, audit=audit)

    events = asyncio.run(_collect_events(executor, _context()))
    llm_call_events = [e for e in events if isinstance(e, LLMCallStarted)]
    assert len(llm_call_events) == 2
    assert llm_call_events[0].iteration_index == 1
    assert llm_call_events[1].iteration_index == 2
    # Second iteration's message_count is greater (assistant + tool messages).
    assert llm_call_events[1].message_count > llm_call_events[0].message_count
