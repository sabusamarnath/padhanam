"""AgentLoopExecutor — hand-rolled LLM-with-tool-loop adapter (D88, S27b).

Implements the ``AgentExecutor`` port at
``contexts/agent/ports/executor.py``. The loop runs one or more
inference calls against the LiteLLM-backed ``InferencePort`` per D4;
between calls, model-issued tool calls are dispatched to the
``AgentRetrievalClient`` (Phase 1: retrieval is the only registered
tool per D88's retrieval-as-only-callable framing). The loop
terminates on content-only responses, on calls to unregistered tools
(Phase 1 returns ``TerminationReason.TOOL_NOT_REGISTERED``), or on
the conventional max-iteration cap of 10.

Audit emission per D26: two events per invocation (start, end) via
the existing ``AuditPort`` (the per-tenant audit chain absorbs the
new event types). The Postgres adapter is the chain authority and
the persisted event with the authoritative ``this_event_hash``
returns on each emit per D88's widened port contract; the agent
result surfaces both hashes for caller deep-linking and chain
verification.

Cost capture per D49 / D88: each LiteLLM call carries a per-call
``cost_usd`` Decimal on the returned ``Completion`` (sourced from
``padhanam.config.cost_for`` inside the inference adapter); the
executor sums per-call cost to produce the invocation aggregate on
``AgentResult.cost_total_usd``. OTel spans for each call land
unchanged through the inference adapter; the agent runtime adds a
parent span wrapping the full invocation so the trace tree is
``agent.invoke`` → ``chat {model}`` × N → retrieval_calls when
present.

Async-over-sync bridge: ``InferencePort.complete`` is sync (the
LiteLLM gateway call is sync per the existing adapter); the
executor offloads via ``asyncio.to_thread`` so the event loop stays
unblocked while retrieval and audit operations run async.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import SpanKind

from contexts.agent.application.ports import (
    InvocationOutcome,
    ToolInvocationResult,
    ToolInvoker,
)
from contexts.agent.ports.executor import (
    AgentExecutor,
    AgentInvocationContext,
    AgentResult,
    AgentSignal,
    TerminationReason,
)
from contexts.audit.domain.events import AuditEvent, GENESIS_HASH, compute_event_hash
from contexts.audit.domain.ports import AuditPort
from contexts.inference.domain.completion import (
    Completion,
    Message,
    ToolDefinition,
)
from contexts.inference.ports import InferencePort

_log = logging.getLogger("contexts.agent.agent_loop_executor")
_tracer = trace.get_tracer("padhanam.agent.loop_executor")

# D88 conventional max-iteration cap. Per-role configuration defers if
# evidence demands; the value here is the single Phase 1 setting.
MAX_ITERATIONS = 10

# The hardcoded retrieval surface from S27b / D88 retires at S28b
# commit 5 per D89. Tool definitions now flow from
# ``EffectiveConstraintBundle.tool_definitions`` (composed at
# ``contexts/agent/application/composition.py`` via
# ``ToolDefinitionsLookup``); tool invocation flows through the
# ``ToolInvoker`` port wired at ``apps/cli/_cross_context.py``.
# Retrieval becomes a tool registered in the tool registry like any
# other tool.


class AgentLoopExecutor(AgentExecutor):
    """Hand-rolled LLM-with-tool-loop executor (D88).

    Constructor wiring:

    - ``inference_port``: the LiteLLM-backed ``InferencePort`` (D4).
      Sync call bridged via ``asyncio.to_thread``.
    - ``tool_invoker``: the ``ToolInvoker`` consumer port at D89.
      The adapter at ``apps/cli/_cross_context.py`` (S28b commit 7)
      composes the tools-context invocation service (classification
      gating + defensive invariant check) with per-tool dispatch
      (Phase 1: retrieval via ``AgentRetrievalClient``). The
      hardcoded retrieval branch from D88 retires here.
    - ``audit_port``: the ``AuditPort`` (D22). The Postgres adapter is
      the chain authority and returns the persisted event with the
      authoritative ``this_event_hash`` per D88's port widening.
    """

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

    async def execute(self, context: AgentInvocationContext) -> AgentResult:
        with _tracer.start_as_current_span(
            "agent.invoke",
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
                "tenant.id": context.tenant_context.tenant_id,
                "tenant.jurisdiction": context.tenant_context.jurisdiction,
            },
        ) as invoke_span:
            input_hash = _hash_text(context.user_input)
            correlation_id = _correlation_id_for(invoke_span, context)

            start_event = await self._emit_start_audit(
                context=context,
                input_hash=input_hash,
                correlation_id=correlation_id,
            )

            (
                response_content,
                signals,
                cost_total,
                iteration_count,
                termination_reason,
                early_termination,
            ) = await self._run_loop(context=context)

            invoke_span.set_attribute("agent.iteration_count", iteration_count)
            invoke_span.set_attribute(
                "agent.termination_reason", termination_reason.value
            )
            invoke_span.set_attribute(
                "agent.cost_total_usd", float(cost_total)
            )
            invoke_span.set_attribute(
                "agent.early_termination", early_termination
            )

            response_hash = _hash_text(response_content)
            end_event = await self._emit_end_audit(
                context=context,
                input_hash=input_hash,
                response_hash=response_hash,
                cost_total=cost_total,
                iteration_count=iteration_count,
                termination_reason=termination_reason,
                correlation_id=correlation_id,
            )

            return AgentResult(
                response_content=response_content,
                signals=tuple(signals),
                cost_total_usd=cost_total,
                iteration_count=iteration_count,
                termination_reason=termination_reason,
                audit_start_hash=start_event.this_event_hash,
                audit_end_hash=end_event.this_event_hash,
                early_termination=early_termination,
            )

    # ------------------------------------------------------------------
    # Loop body
    # ------------------------------------------------------------------

    async def _run_loop(
        self,
        *,
        context: AgentInvocationContext,
    ) -> tuple[str, list[AgentSignal], Decimal, int, TerminationReason, bool]:
        bundle = context.effective_bundle
        messages: list[Message] = [
            Message(role="system", content=bundle.system_prompt)
        ]
        for prior in context.conversation_history:
            messages.append(Message(role=prior.role, content=prior.content))
        messages.append(Message(role="user", content=context.user_input))

        # Per D89 commit 5, the tool definitions list arrives on the
        # invocation context (resolved by ``ToolDefinitionsLookup`` at
        # ``invoke_agent`` use case time and threaded through here).
        # The executor passes the list through to the LiteLLM call
        # verbatim. Empty tuple → loop runs without tools.
        tools: list[ToolDefinition] = list(context.tool_definitions)

        cost_total = Decimal("0")
        signals: list[AgentSignal] = []
        iteration = 0
        response_content = ""
        termination_reason: TerminationReason = TerminationReason.ERROR
        early_termination = False

        while iteration < MAX_ITERATIONS:
            iteration += 1
            completion: Completion = await asyncio.to_thread(
                self._inference_port.complete,
                messages=messages,
                model=bundle.model_selection,
                tenant_context=context.tenant_context,
                tools=tools,
            )
            cost_total += completion.cost_usd

            if not completion.tool_calls:
                response_content = completion.text
                termination_reason = TerminationReason.CONTENT
                break

            messages.append(
                Message(
                    role="assistant",
                    content=completion.text or "",
                    tool_calls=completion.tool_calls,
                )
            )

            # Per D89 commit 5: dispatch every tool call through the
            # ``ToolInvoker`` port. The adapter at
            # ``apps/cli/_cross_context.py`` (commit 7) composes the
            # tools-context invocation service (classification gating
            # + defensive invariant check) with per-tool dispatch.
            # INVARIANT_BLOCKED or TOOL_NOT_REGISTERED outcomes
            # terminate the loop with the corresponding
            # ``TerminationReason``; OK appends the formatted tool
            # result and the loop continues; ERROR surfaces the
            # message in response content and terminates.
            early_break = False
            for tool_call in completion.tool_calls:
                result: ToolInvocationResult = await self._tool_invoker(
                    tool_call=tool_call,
                    tenant_context=context.tenant_context,
                )

                if result.outcome is InvocationOutcome.INVARIANT_BLOCKED:
                    response_content = (
                        completion.text or result.message or result.payload
                    )
                    termination_reason = TerminationReason.INVARIANT_BLOCKED
                    early_termination = True
                    signals.append(
                        AgentSignal(
                            kind="invariant_blocked",
                            payload={
                                "tool_name": tool_call.name,
                                "invariant_index": (
                                    result.invariant_index
                                    if result.invariant_index is not None
                                    else 0
                                ),
                                "message": result.message,
                            },
                        )
                    )
                    early_break = True
                    break

                if result.outcome is InvocationOutcome.TOOL_NOT_REGISTERED:
                    response_content = (
                        completion.text
                        or result.message
                        or (
                            f"(model attempted to call unregistered tool "
                            f"{tool_call.name!r})"
                        )
                    )
                    termination_reason = TerminationReason.TOOL_NOT_REGISTERED
                    early_termination = True
                    signals.append(
                        AgentSignal(
                            kind="unregistered_tool_attempted",
                            payload={"names": (tool_call.name,)},
                        )
                    )
                    early_break = True
                    break

                # OK or ERROR — both append the payload as a tool-
                # role message and continue the loop. ERROR carries
                # an explanatory string in payload so the LLM can
                # react; OK carries the tool's formatted result.
                messages.append(
                    Message(
                        role="tool",
                        content=result.payload,
                        tool_call_id=tool_call.id,
                    )
                )
                signals.append(
                    AgentSignal(
                        kind="tool_invoked",
                        payload={
                            "tool_name": tool_call.name,
                            "outcome": result.outcome.value,
                        },
                    )
                )

            if early_break:
                break
        else:
            # The while loop completed iteration MAX_ITERATIONS without
            # the ``break``: the cap fired. The last completion still
            # carries content (or an empty string if the model only
            # produced tool calls); surface what we have.
            response_content = (
                completion.text
                or "(no content produced before the iteration cap fired)"
            )
            termination_reason = TerminationReason.MAX_ITERATIONS
            early_termination = True
            signals.append(
                AgentSignal(
                    kind="max_iterations_terminated",
                    payload={"cap": MAX_ITERATIONS},
                )
            )

        return (
            response_content,
            signals,
            cost_total,
            iteration,
            termination_reason,
            early_termination,
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


# Per D89 commit 5, retrieval-specific parsing
# (``_parse_retrieval_query``) and chunk-formatting
# (``_format_chunks_as_tool_result``) relocated to the wiring layer
# at ``apps/cli/_cross_context.py`` (S28b commit 7), where the
# ``ToolInvoker`` adapter dispatches each tool to its specific
# implementation. The executor stays tool-agnostic.
