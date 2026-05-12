"""OTel span hierarchy tests for AgentLoopExecutor (D90 commit 6).

Verifies the nested span tree commitment from D90: invocation →
iteration → (llm_call, tool_call). Drives the executor with an in-
memory OTel exporter; collects exported spans; asserts parent-child
relationships, attribute presence, and cost roll-up arithmetic.

The LiteLLM adapter is bypassed here — the scripted streaming
inference port from the main executor tests does not emit a
gen_ai.llm_call span (that's the adapter's responsibility, exercised
in the inference adapter tests at S29b commit 4 and in the integration
test against the live stack at commit 9). These tests focus on the
two new span types (agent.iteration, agent.tool_call) that the
executor itself emits.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from decimal import Decimal
from typing import Any, AsyncIterator
from uuid import UUID, uuid4

import pytest
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from contexts.agent.adapters.outbound.agent_loop_executor import (
    AgentLoopExecutor,
)
from contexts.agent.application.ports import (
    InvocationOutcome,
    ToolInvocationResult,
)
from contexts.agent.domain.effective_bundle import EffectiveConstraintBundle
from contexts.agent.domain.events import AgentEvent
from contexts.agent.ports.executor import AgentInvocationContext
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
    tool_definitions: tuple[ToolDefinition, ...] = (),
    tool_classifications: dict[str, str] | None = None,
) -> AgentInvocationContext:
    return AgentInvocationContext(
        tenant_context=_TENANT_A,
        agent_template_id=uuid4(),
        agent_revision_version=1,
        role_template_id=uuid4(),
        role_revision_version=1,
        methodology_template_id=None,
        methodology_version=None,
        effective_bundle=_bundle(),
        user_input="frame this for me",
        tool_definitions=tool_definitions,
        tool_classifications=tool_classifications
        or {"retrieval": "read_only"},
    )


class _ScriptedStreamingInference:
    def __init__(self, scripted: list[list[CompletionChunk]]) -> None:
        self._scripted = list(scripted)
        self.calls = 0

    def complete(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError(
            "streaming-only executor calls stream_complete"
        )

    async def stream_complete(
        self,
        messages: Sequence[Message],
        model: str | None,
        tenant_context: TenantContext,
        tools: Sequence[ToolDefinition] = (),
    ) -> AsyncIterator[CompletionChunk]:
        self.calls += 1
        for chunk in self._scripted.pop(0):
            yield chunk


class _ScriptedInvoker:
    def __init__(self, results: list[ToolInvocationResult]) -> None:
        self._results = list(results)

    async def __call__(
        self,
        *,
        tool_call: ToolCall,
        tenant_context: TenantContext,
    ) -> ToolInvocationResult:
        return self._results.pop(0)


class _ChainingFakeAuditPort:
    def __init__(self) -> None:
        self._chain: list[AuditEvent] = []

    async def emit(self, event: AuditEvent) -> AuditEvent:
        previous = (
            self._chain[-1].this_event_hash
            if self._chain
            else GENESIS_HASH
        )
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
        self._chain.append(persisted)
        return persisted


@pytest.fixture
def trace_capture() -> Any:
    """Attach an in-memory span exporter to the current TracerProvider.

    OTel guards against multi-replace of the global TracerProvider
    within a single process (raises a warning and ignores subsequent
    set calls); this fixture instead attaches a fresh SimpleSpanProcessor
    + InMemorySpanExporter to whichever provider is current. Each test
    gets a fresh exporter (so spans from prior tests do not leak in)
    and the processor is shut down at teardown so the provider's
    processor list does not grow unbounded across the session.

    If the current provider is the SDK's no-op (no add_span_processor
    method), promote to a real TracerProvider for the duration of the
    test.
    """
    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)

    current = trace.get_tracer_provider()
    add_span_processor = getattr(current, "add_span_processor", None)
    promoted_provider: TracerProvider | None = None
    if add_span_processor is None:
        promoted_provider = TracerProvider(
            resource=Resource.create({"service.name": "padhanam-agent-test"})
        )
        promoted_provider.add_span_processor(processor)
        trace.set_tracer_provider(promoted_provider)
    else:
        add_span_processor(processor)

    try:
        yield exporter
    finally:
        processor.shutdown()
        exporter.shutdown()
        if promoted_provider is not None:
            # Best-effort restore; if another test promoted first, we
            # leave the global as-is.
            pass


def _terminal_chunk(
    *,
    cost: str = "0.001",
    tool_calls: tuple[ToolCall, ...] = (),
    finish_reason: str = "stop",
) -> CompletionChunk:
    return CompletionChunk(
        text_delta="",
        is_final=True,
        finish_reason=finish_reason,
        model="qwen2.5:7b",
        tool_calls=tool_calls,
        usage=TokenUsage(input_tokens=10, output_tokens=4),
        cost_usd=Decimal(cost),
    )


def _content_chunks(text: str, cost: str = "0.001") -> list[CompletionChunk]:
    return [
        CompletionChunk(text_delta=text, is_final=False),
        _terminal_chunk(cost=cost),
    ]


def test_span_tree_has_invocation_parent_iteration_children(
    trace_capture: InMemorySpanExporter,
) -> None:
    """Content-only invocation: one agent.invocation span with one
    agent.iteration child."""
    inference = _ScriptedStreamingInference([_content_chunks("hi", cost="0.005")])
    invoker = _ScriptedInvoker([])
    audit = _ChainingFakeAuditPort()
    executor = AgentLoopExecutor(
        inference_port=inference,
        tool_invoker=invoker,
        audit_port=audit,
    )

    async def drive() -> list[AgentEvent]:
        return [e async for e in executor.execute(_context())]

    asyncio.run(drive())

    spans = trace_capture.get_finished_spans()
    by_name: dict[str, list[Any]] = {}
    for s in spans:
        by_name.setdefault(s.name, []).append(s)

    assert "agent.invocation" in by_name
    assert "agent.iteration" in by_name
    assert len(by_name["agent.invocation"]) == 1
    assert len(by_name["agent.iteration"]) == 1

    inv = by_name["agent.invocation"][0]
    it = by_name["agent.iteration"][0]
    # Iteration's parent is the invocation.
    assert it.parent.span_id == inv.context.span_id


def test_iteration_span_carries_index_cost_and_duration_attributes(
    trace_capture: InMemorySpanExporter,
) -> None:
    inference = _ScriptedStreamingInference([_content_chunks("done", cost="0.012")])
    invoker = _ScriptedInvoker([])
    audit = _ChainingFakeAuditPort()
    executor = AgentLoopExecutor(
        inference_port=inference,
        tool_invoker=invoker,
        audit_port=audit,
    )

    async def drive() -> None:
        async for _ in executor.execute(_context()):
            pass

    asyncio.run(drive())

    spans = trace_capture.get_finished_spans()
    iteration_span = next(s for s in spans if s.name == "agent.iteration")
    assert iteration_span.attributes["iteration.index"] == 1
    assert iteration_span.attributes["iteration.cost_usd"] == pytest.approx(
        0.012
    )
    assert "iteration.duration_ms" in iteration_span.attributes


def test_tool_call_span_nests_under_iteration_with_attributes(
    trace_capture: InMemorySpanExporter,
) -> None:
    """A tool-call iteration spawns an agent.tool_call span as a child
    of agent.iteration; tool.name and tool.classification are set."""
    inference = _ScriptedStreamingInference(
        [
            [
                _terminal_chunk(
                    cost="0.001",
                    finish_reason="tool_calls",
                    tool_calls=(
                        ToolCall(
                            id="c1",
                            name="retrieval",
                            arguments_json='{"query": "x"}',
                        ),
                    ),
                )
            ],
            _content_chunks("final", cost="0.002"),
        ]
    )
    invoker = _ScriptedInvoker(
        [ToolInvocationResult(outcome=InvocationOutcome.OK, payload="x")]
    )
    audit = _ChainingFakeAuditPort()
    executor = AgentLoopExecutor(
        inference_port=inference,
        tool_invoker=invoker,
        audit_port=audit,
    )

    async def drive() -> None:
        async for _ in executor.execute(_context()):
            pass

    asyncio.run(drive())

    spans = trace_capture.get_finished_spans()
    iteration_spans = [s for s in spans if s.name == "agent.iteration"]
    tool_spans = [s for s in spans if s.name == "agent.tool_call"]
    assert len(tool_spans) == 1
    tool_span = tool_spans[0]

    assert tool_span.attributes["tool.name"] == "retrieval"
    assert tool_span.attributes["tool.classification"] == "read_only"
    assert tool_span.attributes["tool.result.status"] == "ok"

    # tool span's parent is the FIRST iteration (the one that issued
    # the tool call).
    first_iteration = next(
        s
        for s in iteration_spans
        if s.attributes["iteration.index"] == 1
    )
    assert tool_span.parent.span_id == first_iteration.context.span_id


def test_invocation_span_carries_rolled_up_total_cost(
    trace_capture: InMemorySpanExporter,
) -> None:
    """The invocation span's agent.total_cost_usd is the sum of iteration costs."""
    inference = _ScriptedStreamingInference(
        [
            [
                _terminal_chunk(
                    cost="0.005",
                    finish_reason="tool_calls",
                    tool_calls=(
                        ToolCall(
                            id="c1",
                            name="retrieval",
                            arguments_json='{"query": "x"}',
                        ),
                    ),
                )
            ],
            _content_chunks("done", cost="0.003"),
        ]
    )
    invoker = _ScriptedInvoker(
        [ToolInvocationResult(outcome=InvocationOutcome.OK, payload="x")]
    )
    audit = _ChainingFakeAuditPort()
    executor = AgentLoopExecutor(
        inference_port=inference,
        tool_invoker=invoker,
        audit_port=audit,
    )

    async def drive() -> None:
        async for _ in executor.execute(_context()):
            pass

    asyncio.run(drive())

    spans = trace_capture.get_finished_spans()
    inv_span = next(s for s in spans if s.name == "agent.invocation")
    assert inv_span.attributes["agent.total_cost_usd"] == pytest.approx(0.008)
    assert inv_span.attributes["agent.iteration_count"] == 2

    iteration_costs = sorted(
        s.attributes["iteration.cost_usd"]
        for s in spans
        if s.name == "agent.iteration"
    )
    assert sum(iteration_costs) == pytest.approx(0.008)
