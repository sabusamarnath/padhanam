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
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from opentelemetry import trace
from opentelemetry.trace import SpanKind

from contexts.agent.application.ports import AgentRetrievalClient, RetrievedChunk
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

# The single tool the agent runtime registers at Phase 1 per D88's
# retrieval-as-only-callable framing. S28b's tool registry generalises
# this surface to multiple tools with classification enforcement. The
# retrieval tool's identity is the well-known UUID seeded by
# ``0009_create_tools_tables`` per D89; the role's allowlist pin
# (post-commit-4 tuple shape) carries this UUID for revision 1.
RETRIEVAL_TOOL_NAME = "retrieval"
RETRIEVAL_TOOL_ID = UUID("00000000-0000-0000-0000-000000000001")

_RETRIEVAL_TOOL_DEFINITION = ToolDefinition(
    name=RETRIEVAL_TOOL_NAME,
    description=(
        "Search the agent's grounded knowledge base for relevant chunks "
        "matching the query. Returns text excerpts ranked by relevance."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The natural-language search query.",
            },
        },
        "required": ["query"],
    },
)


class AgentLoopExecutor(AgentExecutor):
    """Hand-rolled LLM-with-tool-loop executor (D88).

    Constructor wiring:

    - ``inference_port``: the LiteLLM-backed ``InferencePort`` (D4).
      Sync call bridged via ``asyncio.to_thread``.
    - ``retrieval_client``: the ``AgentRetrievalClient`` consumer port
      (D88). The adapter at ``apps/cli/_cross_context.py`` composes
      the ingestion context's ``search_vector`` and ``traverse_graph``
      per the role's retrieval strategy.
    - ``audit_port``: the ``AuditPort`` (D22). The Postgres adapter is
      the chain authority and returns the persisted event with the
      authoritative ``this_event_hash`` per D88's port widening.
    """

    def __init__(
        self,
        *,
        inference_port: InferencePort,
        retrieval_client: AgentRetrievalClient,
        audit_port: AuditPort,
    ) -> None:
        self._inference_port = inference_port
        self._retrieval_client = retrieval_client
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

        # Phase 1: register the retrieval tool only when the role's
        # tool_allowlist permits it (after composition with the
        # methodology's tighten). Per D89 commit 4 the allowlist
        # carries pinned ``ToolAllowlistEntry`` entries; the retrieval
        # match is by ``tool_id`` against the seeded retrieval UUID.
        # An empty allowlist or one that does not pin retrieval runs
        # the loop without tools, producing a single content turn or
        # terminating early on a model-issued unknown tool call.
        # Commit 5 replaces this hardcoded branch with
        # ``ToolDefinitionsLookup`` from the tools context.
        tools: list[ToolDefinition] = []
        if any(e.tool_id == RETRIEVAL_TOOL_ID for e in bundle.tool_allowlist):
            tools.append(_RETRIEVAL_TOOL_DEFINITION)

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

            unknown_tools = [
                tc.name
                for tc in completion.tool_calls
                if tc.name != RETRIEVAL_TOOL_NAME
            ]
            if unknown_tools:
                response_content = (
                    completion.text
                    or (
                        f"(model attempted to call unregistered tools at "
                        f"Phase 1: {unknown_tools!r}; S28b's tool registry "
                        f"will resolve)"
                    )
                )
                termination_reason = TerminationReason.TOOL_NOT_REGISTERED
                early_termination = True
                signals.append(
                    AgentSignal(
                        kind="unregistered_tool_attempted",
                        payload={"names": tuple(unknown_tools)},
                    )
                )
                break

            messages.append(
                Message(
                    role="assistant",
                    content=completion.text or "",
                    tool_calls=completion.tool_calls,
                )
            )

            for tool_call in completion.tool_calls:
                query = _parse_retrieval_query(tool_call.arguments_json)
                chunks = await self._retrieval_client(
                    query=query,
                    tenant_context=context.tenant_context,
                    retrieval_strategy=bundle.retrieval_strategy,
                    filter_tree=bundle.filter_tree,
                    top_k=bundle.top_k,
                    min_score=bundle.min_score,
                )
                chunks_tuple: tuple[RetrievedChunk, ...] = tuple(chunks)
                messages.append(
                    Message(
                        role="tool",
                        content=_format_chunks_as_tool_result(chunks_tuple),
                        tool_call_id=tool_call.id,
                    )
                )
                signals.append(
                    AgentSignal(
                        kind="retrieval_performed",
                        payload={
                            "query": query,
                            "chunk_count": len(chunks_tuple),
                            "top_score": (
                                chunks_tuple[0].score if chunks_tuple else 0.0
                            ),
                        },
                    )
                )
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


def _parse_retrieval_query(arguments_json: str) -> str:
    """Parse the model-issued retrieval-tool arguments.

    The OpenAI function-calling shape that LiteLLM normalises passes
    ``arguments`` as a JSON string. A well-behaved model produces
    ``{"query": "..."}``; a malformed payload yields an empty query
    string rather than raising, which lets the loop produce a
    structured no-result tool message rather than terminating the
    invocation with an error.
    """
    try:
        parsed = json.loads(arguments_json)
    except (ValueError, TypeError):
        _log.warning(
            "retrieval tool arguments not parseable as JSON: %r",
            arguments_json,
        )
        return ""
    if not isinstance(parsed, dict):
        return ""
    query = parsed.get("query", "")
    return str(query) if query is not None else ""


def _format_chunks_as_tool_result(
    chunks: tuple[RetrievedChunk, ...],
) -> str:
    """Format retrieved chunks as a single tool-result string.

    The shape is human-readable so the LLM can consume it as a tool
    message verbatim. Empty results produce a structured empty marker
    that signals "no matches" rather than an empty string (the LLM may
    interpret an empty tool message as a tool execution failure).
    """
    if not chunks:
        return "(no chunks matched the query)"
    return "\n\n".join(
        f"[score={c.score:.3f}] {c.text}" for c in chunks
    )
