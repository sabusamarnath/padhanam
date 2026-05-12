"""Unit tests for AgentLoopExecutor (D88, S27b).

Covers the control-flow shape: content-only single turn, single tool
call then content, two tool calls then content, unknown-tool branch,
max-iteration cap. Plus audit emission and per-call cost aggregation.

The executor's collaborators (InferencePort, AgentRetrievalClient,
AuditPort) are faked at the Protocol level; the real Postgres adapter
and the real LiteLLM gateway are exercised at the integration test
(S27b commit 8). Faking at the port boundary keeps each unit test
small and fast.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any, Sequence
from uuid import UUID, uuid4

import pytest

from contexts.agent.adapters.outbound.agent_loop_executor import (
    AgentLoopExecutor,
    MAX_ITERATIONS,
)
from contexts.agent.domain.effective_bundle import EffectiveConstraintBundle
from contexts.agent.ports.executor import (
    AgentInvocationContext,
    TerminationReason,
)
from contexts.agent.application.ports import RetrievedChunk
from contexts.audit.domain.events import AuditEvent, GENESIS_HASH, compute_event_hash
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

# Well-known retrieval tool UUIDs per D89's commit-2 seed.
_RETRIEVAL_ALLOWLIST_ENTRY = ToolAllowlistEntry(
    tool_id=UUID("00000000-0000-0000-0000-000000000001"),
    revision_id=UUID("00000000-0000-0000-0000-000000000002"),
)


def _bundle(
    tools: tuple[ToolAllowlistEntry, ...] = (_RETRIEVAL_ALLOWLIST_ENTRY,),
) -> EffectiveConstraintBundle:
    return EffectiveConstraintBundle(
        system_prompt="be helpful",
        tool_allowlist=tools,
        retrieval_strategy={"primary": "vector"},
        filter_tree={},
        top_k=5,
        min_score=Decimal("0.5"),
        model_selection="qwen2.5:7b",
    )


def _context(
    *,
    tools: tuple[ToolAllowlistEntry, ...] = (_RETRIEVAL_ALLOWLIST_ENTRY,),
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
        effective_bundle=_bundle(tools=tools),
        user_input="help me frame this problem",
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
    """Replays a queue of pre-canned Completions in order.

    Tests script the model's behaviour by adding completions in the
    order the executor will consume them. Each call captures the
    request shape so assertions can inspect message lists and tool
    payloads.
    """

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


class _ScriptedRetrievalClient:
    """Replays a queue of pre-canned chunk-result tuples."""

    def __init__(self, results: list[tuple[RetrievedChunk, ...]]) -> None:
        self._results = list(results)
        self.calls: list[dict[str, Any]] = []

    async def __call__(
        self,
        *,
        query: str,
        tenant_context: TenantContext,
        retrieval_strategy,
        filter_tree,
        top_k: int,
        min_score: Decimal,
    ) -> tuple[RetrievedChunk, ...]:
        self.calls.append(
            {
                "query": query,
                "tenant_context": tenant_context,
                "retrieval_strategy": retrieval_strategy,
                "filter_tree": filter_tree,
                "top_k": top_k,
                "min_score": min_score,
            }
        )
        if not self._results:
            raise AssertionError("ScriptedRetrievalClient exhausted")
        return self._results.pop(0)


class _ChainingFakeAuditPort:
    """In-memory audit port that mimics the Postgres chain authority.

    Builds an in-memory chain: each emit reads the chain tail, computes
    the authoritative hashes, appends a persisted event, and returns
    it. Mirrors the per-tenant scoping by keying the chain on tenant_id
    so cross-tenant isolation can be asserted.
    """

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


# 1. Content-only termination at iteration 1.

def test_content_only_response_terminates_at_iteration_one() -> None:
    inference = _ScriptedInferencePort(
        [_completion(text="here is your framed problem", cost="0.001")]
    )
    retrieval = _ScriptedRetrievalClient([])
    audit = _ChainingFakeAuditPort()
    executor = AgentLoopExecutor(
        inference_port=inference,
        retrieval_client=retrieval,
        audit_port=audit,
    )

    result = asyncio.run(executor.execute(_context()))

    assert result.response_content == "here is your framed problem"
    assert result.iteration_count == 1
    assert result.termination_reason == TerminationReason.CONTENT
    assert result.cost_total_usd == Decimal("0.001")
    assert result.early_termination is False
    assert result.signals == ()
    assert len(inference.calls) == 1
    assert len(retrieval.calls) == 0


# 2. Audit emission: two events per invocation, chained.

def test_audit_emits_start_and_end_events_chained() -> None:
    inference = _ScriptedInferencePort([_completion(text="ok")])
    audit = _ChainingFakeAuditPort()
    executor = AgentLoopExecutor(
        inference_port=inference,
        retrieval_client=_ScriptedRetrievalClient([]),
        audit_port=audit,
    )

    result = asyncio.run(executor.execute(_context()))

    chain = audit.chains[_TENANT_A.tenant_id]
    assert len(chain) == 2
    assert chain[0].action_verb == "agent.invoke.start"
    assert chain[1].action_verb == "agent.invoke.end"
    # Chain integrity: end's previous_event_hash equals start's
    # this_event_hash; both hashes are non-empty and 64-char hex.
    assert chain[1].previous_event_hash == chain[0].this_event_hash
    assert len(chain[0].this_event_hash) == 64
    assert len(chain[1].this_event_hash) == 64
    # AgentResult surfaces both hashes.
    assert result.audit_start_hash == chain[0].this_event_hash
    assert result.audit_end_hash == chain[1].this_event_hash


def test_audit_payload_carries_methodology_lineage_when_set() -> None:
    inference = _ScriptedInferencePort([_completion(text="ok")])
    audit = _ChainingFakeAuditPort()
    methodology_id = uuid4()
    ctx = _context(methodology_id=methodology_id)
    executor = AgentLoopExecutor(
        inference_port=inference,
        retrieval_client=_ScriptedRetrievalClient([]),
        audit_port=audit,
    )

    asyncio.run(executor.execute(ctx))

    start = audit.chains[_TENANT_A.tenant_id][0]
    assert start.after_state["methodology_template_id"] == str(methodology_id)
    assert start.after_state["methodology_version"] == 1


def test_audit_end_payload_carries_termination_and_cost() -> None:
    inference = _ScriptedInferencePort(
        [_completion(text="done", cost="0.0042")]
    )
    audit = _ChainingFakeAuditPort()
    executor = AgentLoopExecutor(
        inference_port=inference,
        retrieval_client=_ScriptedRetrievalClient([]),
        audit_port=audit,
    )

    asyncio.run(executor.execute(_context()))

    end = audit.chains[_TENANT_A.tenant_id][1]
    assert end.after_state["termination_reason"] == "content"
    assert end.after_state["iteration_count"] == 1
    assert end.after_state["cost_total_usd"] == "0.0042"


# 3. Tool loop: single retrieval then content.

def test_single_tool_call_then_content_terminates_at_iteration_two() -> None:
    """The agent issues one retrieval call, gets chunks, then produces
    content."""
    inference = _ScriptedInferencePort(
        [
            _completion(
                tool_calls=(
                    ToolCall(
                        id="call_1",
                        name="retrieval",
                        arguments_json='{"query": "What is LVT?"}',
                    ),
                ),
                cost="0.001",
            ),
            _completion(text="LVT is...", cost="0.002"),
        ]
    )
    chunk = RetrievedChunk(
        text="LVT means Land Value Tax", source_id=uuid4(), score=0.92
    )
    retrieval = _ScriptedRetrievalClient([(chunk,)])
    audit = _ChainingFakeAuditPort()
    executor = AgentLoopExecutor(
        inference_port=inference,
        retrieval_client=retrieval,
        audit_port=audit,
    )

    result = asyncio.run(executor.execute(_context()))

    assert result.response_content == "LVT is..."
    assert result.iteration_count == 2
    assert result.termination_reason == TerminationReason.CONTENT
    assert result.cost_total_usd == Decimal("0.003")
    assert len(retrieval.calls) == 1
    # The retrieval client received the parsed query argument and the
    # bundle's strategy/filter_tree/top_k/min_score.
    assert retrieval.calls[0]["query"] == "What is LVT?"
    assert retrieval.calls[0]["top_k"] == 5
    assert retrieval.calls[0]["min_score"] == Decimal("0.5")
    # signals carry the retrieval_performed event with chunk_count.
    retrieval_signals = [s for s in result.signals if s.kind == "retrieval_performed"]
    assert len(retrieval_signals) == 1
    assert retrieval_signals[0].payload["chunk_count"] == 1
    assert retrieval_signals[0].payload["query"] == "What is LVT?"


def test_second_inference_call_sees_assistant_tool_calls_and_tool_result() -> None:
    """After the first retrieval call resolves, the executor appends
    the assistant's tool_calls and the tool result; the second
    inference call sees both in the message list."""
    inference = _ScriptedInferencePort(
        [
            _completion(
                tool_calls=(
                    ToolCall(
                        id="call_xyz",
                        name="retrieval",
                        arguments_json='{"query": "x"}',
                    ),
                ),
            ),
            _completion(text="answer"),
        ]
    )
    chunk = RetrievedChunk(text="chunk-content", source_id=uuid4(), score=0.7)
    retrieval = _ScriptedRetrievalClient([(chunk,)])
    audit = _ChainingFakeAuditPort()
    executor = AgentLoopExecutor(
        inference_port=inference,
        retrieval_client=retrieval,
        audit_port=audit,
    )

    asyncio.run(executor.execute(_context()))

    second_call_messages = inference.calls[1][0]
    # Layout: system, user, assistant(tool_calls), tool(result)
    assert len(second_call_messages) == 4
    assert second_call_messages[0].role == "system"
    assert second_call_messages[1].role == "user"
    assert second_call_messages[2].role == "assistant"
    assert second_call_messages[2].tool_calls[0].id == "call_xyz"
    assert second_call_messages[3].role == "tool"
    assert second_call_messages[3].tool_call_id == "call_xyz"
    assert "chunk-content" in second_call_messages[3].content


# 4. Unknown-tool branch.

def test_unknown_tool_call_terminates_with_tool_not_registered() -> None:
    inference = _ScriptedInferencePort(
        [
            _completion(
                tool_calls=(
                    ToolCall(
                        id="call_bad",
                        name="send_email",
                        arguments_json='{"to": "bob@example.com"}',
                    ),
                ),
            ),
        ]
    )
    audit = _ChainingFakeAuditPort()
    executor = AgentLoopExecutor(
        inference_port=inference,
        retrieval_client=_ScriptedRetrievalClient([]),
        audit_port=audit,
    )

    result = asyncio.run(executor.execute(_context()))

    assert result.termination_reason == TerminationReason.TOOL_NOT_REGISTERED
    assert result.early_termination is True
    assert "send_email" in result.response_content
    signals = [s for s in result.signals if s.kind == "unregistered_tool_attempted"]
    assert len(signals) == 1
    assert signals[0].payload["names"] == ("send_email",)
    # End audit row records the termination.
    end = audit.chains[_TENANT_A.tenant_id][1]
    assert end.after_state["termination_reason"] == "tool_not_registered"


# 5. Tool-allowlist enforcement: no retrieval in bundle = no tool definition.

def test_empty_tool_allowlist_passes_no_tools_to_inference() -> None:
    inference = _ScriptedInferencePort([_completion(text="ok")])
    audit = _ChainingFakeAuditPort()
    executor = AgentLoopExecutor(
        inference_port=inference,
        retrieval_client=_ScriptedRetrievalClient([]),
        audit_port=audit,
    )

    asyncio.run(executor.execute(_context(tools=())))

    # The first (and only) inference call gets an empty tools list.
    _, _, _, tools_sent = inference.calls[0]
    assert tools_sent == []


# 6. Max-iteration cap.

def test_max_iterations_cap_terminates_with_max_iterations() -> None:
    """The agent issues retrieval calls indefinitely; after the cap
    (MAX_ITERATIONS) iterations without content, the loop terminates
    with TerminationReason.MAX_ITERATIONS."""
    # Script MAX_ITERATIONS tool-call responses; the last completion's
    # text is what the executor surfaces with the cap.
    completions = [
        _completion(
            text=f"thinking {i}",
            tool_calls=(
                ToolCall(
                    id=f"call_{i}",
                    name="retrieval",
                    arguments_json='{"query": "x"}',
                ),
            ),
        )
        for i in range(MAX_ITERATIONS)
    ]
    inference = _ScriptedInferencePort(completions)
    chunks = [
        (RetrievedChunk(text=f"chunk {i}", source_id=uuid4(), score=0.5),)
        for i in range(MAX_ITERATIONS)
    ]
    retrieval = _ScriptedRetrievalClient(chunks)
    audit = _ChainingFakeAuditPort()
    executor = AgentLoopExecutor(
        inference_port=inference,
        retrieval_client=retrieval,
        audit_port=audit,
    )

    result = asyncio.run(executor.execute(_context()))

    assert result.iteration_count == MAX_ITERATIONS
    assert result.termination_reason == TerminationReason.MAX_ITERATIONS
    assert result.early_termination is True
    # The signals list carries the max_iterations_terminated marker.
    max_signals = [
        s for s in result.signals if s.kind == "max_iterations_terminated"
    ]
    assert len(max_signals) == 1
    assert max_signals[0].payload["cap"] == MAX_ITERATIONS


# 7. Cost aggregation.

def test_cost_total_sums_across_calls() -> None:
    inference = _ScriptedInferencePort(
        [
            _completion(
                tool_calls=(
                    ToolCall(
                        id="c1",
                        name="retrieval",
                        arguments_json='{"query": "x"}',
                    ),
                ),
                cost="0.0010",
            ),
            _completion(text="done", cost="0.0025"),
        ]
    )
    retrieval = _ScriptedRetrievalClient(
        [(RetrievedChunk(text="x", source_id=uuid4(), score=0.6),)]
    )
    audit = _ChainingFakeAuditPort()
    executor = AgentLoopExecutor(
        inference_port=inference,
        retrieval_client=retrieval,
        audit_port=audit,
    )

    result = asyncio.run(executor.execute(_context()))

    assert result.cost_total_usd == Decimal("0.0035")
