"""AgentLoopExecutor — streaming LLM-with-tool-loop adapter (D88, D89, D90; S27b→S29b).

Implements the ``AgentExecutor`` port at
``contexts/agent/ports/executor.py``. Per D90 (S29b) the executor is
streaming-only: ``execute(context)`` is an async generator yielding
``AgentEvent`` values from the eleven-type domain vocabulary. Non-
streaming callers wrap via ``contexts/agent/application/collect.py``'s
``collect_to_result`` helper.

Loop shape: drive LLM-with-tool iterations via
``InferencePort.stream_complete`` (D90 commit 4), accumulate text
fragments into ``ContentDelta`` events as they arrive, branch on the
terminal-chunk's tool calls, dispatch each via the ``ToolInvoker`` port
(D89 commit 5), terminate on content / max-iterations cap / tool-not-
registered / invariant-blocked. ``MAX_ITERATIONS`` stays at 10 per D88.

Audit per D26: two events per invocation regardless of termination
reason (D90 sub-choice 2 Option C). The start audit fires before the
first event yields; the end audit fires after the loop terminates and
before the terminal ``AgentEvent`` yields. The terminal event carries
both audit hashes so consumers can deep-link into the audit chain or
verify integrity.

Failure handling: any unhandled exception inside the loop emits an
``InvocationFailed`` event with ``partial_audit_chain_state`` carrying
whichever audit hashes have landed at the failure point (empty when
the failure is pre-start-audit; one hash when start-only; the helper
in collect_to_result handles both).

Trace span: one ``agent.invocation`` span wraps the whole loop with
tenant + agent attributes; the LiteLLM adapter's ``chat {model}`` span
nests as a child via OTel context propagation (one per iteration's
stream_complete call). The nested ``agent.iteration`` and
``agent.tool_call`` spans land at commit 6 per D90's nested span
hierarchy commitment.

Cost capture per D49 / D90: per-iteration cost from the terminal
``CompletionChunk.cost_usd``; per-invocation total sums per-iteration
costs. Surfaced on ``IterationCompleted`` (per iteration) and on
``InvocationCompleted`` (total).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, AsyncIterator
from uuid import UUID, uuid4

from opentelemetry import trace
from opentelemetry.trace import SpanKind

from contexts.agent.application.ports import (
    InvocationOutcome,
    ToolInvocationResult,
    ToolInvoker,
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
from contexts.agent.ports.executor import (
    AgentExecutor,
    AgentInvocationContext,
)
from contexts.audit.domain.events import AuditEvent, GENESIS_HASH, compute_event_hash
from contexts.audit.domain.ports import AuditPort
from contexts.inference.domain.completion import (
    CompletionChunk,
    Message,
    ToolDefinition,
)
from contexts.inference.ports import InferencePort

_log = logging.getLogger("contexts.agent.agent_loop_executor")
_tracer = trace.get_tracer("padhanam.agent.loop_executor")

# D88 conventional max-iteration cap; preserved at D90 per the streaming
# refactor's no-scope-creep discipline.
MAX_ITERATIONS = 10


# D89's three-to-three mapping (financial→1, communication→2, legal→3).
# Used to derive the classification string when a tool invocation
# returns INVARIANT_BLOCKED so the InvariantBlocked event surfaces a
# human-readable classification rather than just the invariant index.
_INVARIANT_INDEX_TO_CLASSIFICATION: dict[int, str] = {
    1: "financial",
    2: "communication",
    3: "legal",
}


class AgentLoopExecutor(AgentExecutor):
    """Streaming hand-rolled LLM-with-tool-loop executor (D88, D89, D90)."""

    def __init__(
        self,
        *,
        inference_port: InferencePort,
        tool_invoker: ToolInvoker,
        audit_port: AuditPort,
    ) -> None:
        self._inference_port = inference_port
        self._tool_invoker = tool_invoker
        self._audit_port = audit_port

    async def execute(
        self, context: AgentInvocationContext
    ) -> AsyncIterator[AgentEvent]:
        invocation_id = uuid4()
        invocation_started_at = datetime.now(timezone.utc)
        bundle = context.effective_bundle
        model_name = bundle.model_selection
        tool_definitions_list = list(context.tool_definitions)

        with _tracer.start_as_current_span(
            "agent.invocation",
            kind=SpanKind.INTERNAL,
            attributes={
                "agent.template_id": str(context.agent_template_id),
                "agent.revision_version": context.agent_revision_version,
                "agent.role_template_id": str(context.role_template_id),
                "agent.methodology_template_id": (
                    str(context.methodology_template_id)
                    if context.methodology_template_id
                    else ""
                ),
                "agent.invocation_id": str(invocation_id),
                "tenant.id": context.tenant_context.tenant_id,
                "tenant.jurisdiction": context.tenant_context.jurisdiction,
                "model.name": model_name,
            },
        ) as invoke_span:
            input_hash = _hash_text(context.user_input)
            correlation_id = _correlation_id_for(invoke_span, context)

            # ---- start audit ----
            try:
                start_event = await self._emit_start_audit(
                    context=context,
                    input_hash=input_hash,
                    correlation_id=correlation_id,
                )
            except Exception as exc:  # noqa: BLE001 — fail safely with partial state
                duration_ms = _ms_since(invocation_started_at)
                yield InvocationFailed(
                    invocation_id=invocation_id,
                    error_type=type(exc).__name__,
                    error_detail=str(exc),
                    partial_audit_chain_state=(),
                    duration_ms=duration_ms,
                )
                return

            yield InvocationStarted(
                invocation_id=invocation_id,
                agent_template_id=context.agent_template_id,
                tenant_context=context.tenant_context,
                model_name=model_name,
                started_at=invocation_started_at,
            )

            # ---- loop scaffold ----
            messages: list[Message] = [
                Message(role="system", content=bundle.system_prompt)
            ]
            for prior in context.conversation_history:
                messages.append(Message(role=prior.role, content=prior.content))
            messages.append(Message(role="user", content=context.user_input))

            cost_total = Decimal("0")
            iteration = 0
            response_content = ""
            termination_reason: TerminationReason | None = None
            blocked_tool_name = ""
            blocked_classification = ""
            iteration_content = ""  # carried across iterations for final response

            try:
                while iteration < MAX_ITERATIONS:
                    iteration += 1
                    iteration_started_at = datetime.now(timezone.utc)
                    yield IterationStarted(
                        invocation_id=invocation_id,
                        iteration_index=iteration,
                        started_at=iteration_started_at,
                    )

                    yield LLMCallStarted(
                        invocation_id=invocation_id,
                        iteration_index=iteration,
                        model_name=model_name,
                        message_count=len(messages),
                        started_at=datetime.now(timezone.utc),
                    )

                    # ---- stream LLM ----
                    content_parts: list[str] = []
                    terminal_chunk: CompletionChunk | None = None
                    async for chunk in self._inference_port.stream_complete(
                        messages=messages,
                        model=model_name,
                        tenant_context=context.tenant_context,
                        tools=tool_definitions_list,
                    ):
                        if chunk.is_final:
                            terminal_chunk = chunk
                            break
                        if chunk.text_delta:
                            content_parts.append(chunk.text_delta)
                            yield ContentDelta(
                                invocation_id=invocation_id,
                                iteration_index=iteration,
                                text_fragment=chunk.text_delta,
                            )

                    if terminal_chunk is None:
                        raise RuntimeError(
                            "inference stream ended without a terminal chunk"
                        )

                    iteration_cost = terminal_chunk.cost_usd
                    cost_total += iteration_cost
                    iteration_content = "".join(content_parts)
                    tool_calls = terminal_chunk.tool_calls

                    # ---- branch: content-only iteration ----
                    if not tool_calls:
                        response_content = iteration_content
                        termination_reason = TerminationReason.CONTENT
                        yield IterationCompleted(
                            invocation_id=invocation_id,
                            iteration_index=iteration,
                            termination_signal="content",
                            duration_ms=_ms_since(iteration_started_at),
                            cost_usd=iteration_cost,
                        )
                        break

                    # ---- branch: tool calls in this iteration ----
                    messages.append(
                        Message(
                            role="assistant",
                            content=iteration_content,
                            tool_calls=tool_calls,
                        )
                    )

                    iteration_terminated_signal: str | None = None

                    for tool_call in tool_calls:
                        classification = context.tool_classifications.get(
                            tool_call.name, "unknown"
                        )
                        yield ToolCallProposed(
                            invocation_id=invocation_id,
                            iteration_index=iteration,
                            tool_name=tool_call.name,
                            arguments=tool_call.arguments_json,
                            classification=classification,
                        )

                        tool_started_at = datetime.now(timezone.utc)
                        result: ToolInvocationResult = await self._tool_invoker(
                            tool_call=tool_call,
                            tenant_context=context.tenant_context,
                        )

                        if result.outcome is InvocationOutcome.INVARIANT_BLOCKED:
                            blocked_tool_name = tool_call.name
                            blocked_classification = (
                                _INVARIANT_INDEX_TO_CLASSIFICATION.get(
                                    result.invariant_index or 0, classification
                                )
                            )
                            response_content = (
                                iteration_content
                                or result.message
                                or result.payload
                            )
                            termination_reason = (
                                TerminationReason.INVARIANT_BLOCKED
                            )
                            iteration_terminated_signal = "invariant_blocked"
                            break

                        if result.outcome is InvocationOutcome.TOOL_NOT_REGISTERED:
                            response_content = (
                                iteration_content
                                or result.message
                                or (
                                    f"(model attempted to call unregistered tool "
                                    f"{tool_call.name!r})"
                                )
                            )
                            termination_reason = (
                                TerminationReason.TOOL_NOT_REGISTERED
                            )
                            iteration_terminated_signal = "tool_not_registered"
                            break

                        # OK / ERROR both proceed through the executing/completed
                        # path; the loop continues regardless. ERROR appends an
                        # explanation as a tool-role message so the LLM can react.
                        yield ToolCallExecuting(
                            invocation_id=invocation_id,
                            iteration_index=iteration,
                            tool_name=tool_call.name,
                            started_at=tool_started_at,
                        )
                        tool_duration_ms = _ms_since(tool_started_at)
                        yield ToolCallCompleted(
                            invocation_id=invocation_id,
                            iteration_index=iteration,
                            tool_name=tool_call.name,
                            success=result.outcome is InvocationOutcome.OK,
                            result_summary=_summarise(result.payload),
                            duration_ms=tool_duration_ms,
                        )
                        messages.append(
                            Message(
                                role="tool",
                                content=result.payload,
                                tool_call_id=tool_call.id,
                            )
                        )

                    iteration_signal_label = (
                        iteration_terminated_signal or "continue"
                    )
                    yield IterationCompleted(
                        invocation_id=invocation_id,
                        iteration_index=iteration,
                        termination_signal=iteration_signal_label,
                        duration_ms=_ms_since(iteration_started_at),
                        cost_usd=iteration_cost,
                    )

                    if iteration_terminated_signal is not None:
                        break
                else:
                    # while-else: max-iteration cap fired
                    response_content = (
                        iteration_content
                        or "(no content produced before the iteration cap fired)"
                    )
                    termination_reason = TerminationReason.MAX_ITERATIONS
            except Exception as exc:  # noqa: BLE001 — runtime error during loop
                duration_ms = _ms_since(invocation_started_at)
                yield InvocationFailed(
                    invocation_id=invocation_id,
                    error_type=type(exc).__name__,
                    error_detail=str(exc),
                    partial_audit_chain_state=(start_event.this_event_hash,),
                    duration_ms=duration_ms,
                )
                return

            assert termination_reason is not None  # set in every loop exit path

            # ---- end audit ----
            response_hash = _hash_text(response_content)
            try:
                end_event = await self._emit_end_audit(
                    context=context,
                    input_hash=input_hash,
                    response_hash=response_hash,
                    cost_total=cost_total,
                    iteration_count=iteration,
                    termination_reason=termination_reason,
                    correlation_id=correlation_id,
                )
            except Exception as exc:  # noqa: BLE001 — end-audit failure
                duration_ms = _ms_since(invocation_started_at)
                yield InvocationFailed(
                    invocation_id=invocation_id,
                    error_type=type(exc).__name__,
                    error_detail=str(exc),
                    partial_audit_chain_state=(start_event.this_event_hash,),
                    duration_ms=duration_ms,
                )
                return

            invoke_span.set_attribute("agent.iteration_count", iteration)
            invoke_span.set_attribute(
                "agent.termination_reason", termination_reason.value
            )
            invoke_span.set_attribute(
                "agent.cost_total_usd", float(cost_total)
            )
            invoke_span.set_attribute(
                "agent.early_termination",
                termination_reason is not TerminationReason.CONTENT,
            )

            duration_ms = _ms_since(invocation_started_at)
            audit_hashes = (
                start_event.this_event_hash,
                end_event.this_event_hash,
            )

            if termination_reason is TerminationReason.INVARIANT_BLOCKED:
                yield InvariantBlocked(
                    invocation_id=invocation_id,
                    classification=blocked_classification,
                    blocked_tool_name=blocked_tool_name,
                    audit_chain_hashes=audit_hashes,
                )
            else:
                yield InvocationCompleted(
                    invocation_id=invocation_id,
                    final_result=response_content,
                    termination_reason=termination_reason,
                    total_cost_usd=cost_total,
                    audit_chain_hashes=audit_hashes,
                    duration_ms=duration_ms,
                )

    # ------------------------------------------------------------------
    # Audit emission
    # ------------------------------------------------------------------

    async def _emit_start_audit(
        self,
        *,
        context: AgentInvocationContext,
        input_hash: str,
        correlation_id: str,
    ) -> AuditEvent:
        event = _draft_event(
            tenant_context=context.tenant_context,
            action_verb="agent.invoke.start",
            resource_type="agent_template",
            resource_id=str(context.agent_template_id),
            correlation_id=correlation_id,
            before_state={},
            after_state={
                "agent_template_id": str(context.agent_template_id),
                "agent_revision_version": context.agent_revision_version,
                "role_template_id": str(context.role_template_id),
                "role_revision_version": context.role_revision_version,
                "methodology_template_id": (
                    str(context.methodology_template_id)
                    if context.methodology_template_id
                    else None
                ),
                "methodology_version": context.methodology_version,
                "input_hash": input_hash,
            },
        )
        return await self._audit_port.emit(event)

    async def _emit_end_audit(
        self,
        *,
        context: AgentInvocationContext,
        input_hash: str,
        response_hash: str,
        cost_total: Decimal,
        iteration_count: int,
        termination_reason: TerminationReason,
        correlation_id: str,
    ) -> AuditEvent:
        event = _draft_event(
            tenant_context=context.tenant_context,
            action_verb="agent.invoke.end",
            resource_type="agent_template",
            resource_id=str(context.agent_template_id),
            correlation_id=correlation_id,
            before_state={"input_hash": input_hash},
            after_state={
                "response_hash": response_hash,
                "cost_total_usd": str(cost_total),
                "iteration_count": iteration_count,
                "termination_reason": termination_reason.value,
            },
        )
        return await self._audit_port.emit(event)


# ----------------------------------------------------------------------
# Module-private helpers
# ----------------------------------------------------------------------


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _correlation_id_for(span, context: AgentInvocationContext) -> str:
    """Derive a correlation id for the invocation.

    Uses the OTel span's trace_id when one is available so the audit
    rows correlate against the trace in Langfuse; falls back to a
    deterministic seed for headless test contexts where no SDK
    tracer is configured.
    """
    ctx = span.get_span_context()
    if ctx.trace_id:
        return format(ctx.trace_id, "032x")
    return f"agent-invoke:{context.agent_template_id}:{datetime.now(timezone.utc).isoformat()}"


def _ms_since(started_at: datetime) -> int:
    return int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)


def _summarise(payload: str, *, max_len: int = 200) -> str:
    """Truncate a tool's payload for ToolCallCompleted.result_summary.

    The event is observability-shaped, not data-carrying; consumers
    that need the full payload pull from the audit row or the trace.
    Truncation keeps event payloads small for renderable surfaces
    (CLI animation, future UI streams).
    """
    if not payload:
        return ""
    if len(payload) <= max_len:
        return payload
    return payload[: max_len - 1] + "…"


def _draft_event(
    *,
    tenant_context,
    action_verb: str,
    resource_type: str,
    resource_id: str,
    correlation_id: str,
    before_state: dict[str, Any],
    after_state: dict[str, Any],
) -> AuditEvent:
    """Compose an AuditEvent with placeholder chain hashes.

    The Postgres adapter is the chain authority and recomputes both
    hashes inside its locking transaction per D37; the placeholders
    here are draft values that the adapter overwrites. Callers depend
    on the adapter's return for the authoritative hash per D88.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    draft_hash = compute_event_hash(
        actor=tenant_context.tenant_id,
        tenant_id=tenant_context.tenant_id,
        jurisdiction=tenant_context.jurisdiction,
        timestamp=timestamp,
        action_verb=action_verb,
        resource_type=resource_type,
        resource_id=resource_id,
        before_state=before_state,
        after_state=after_state,
        correlation_id=correlation_id,
        previous_event_hash=GENESIS_HASH,
    )
    return AuditEvent(
        actor=tenant_context.tenant_id,
        tenant_id=tenant_context.tenant_id,
        jurisdiction=tenant_context.jurisdiction,
        timestamp=timestamp,
        action_verb=action_verb,
        resource_type=resource_type,
        resource_id=resource_id,
        before_state=before_state,
        after_state=after_state,
        correlation_id=correlation_id,
        previous_event_hash=GENESIS_HASH,
        this_event_hash=draft_hash,
    )
