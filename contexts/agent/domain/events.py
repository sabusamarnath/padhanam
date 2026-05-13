"""AgentEvent vocabulary — the runtime's state-machine surface (D90, S29b).

Eleven frozen-dataclass event types compose the discriminated union
``AgentEvent``. The agent runtime yields events of this type from
``AgentExecutor.execute(...)`` (D90 sub-choice 3); consumers branch on
type for renderable observability (CLI animation, future UI surfaces,
the SSE transport at ``apps/api/routers/agent.py``).

Domain placement (D90 sub-choice 4): events live at the domain layer so
the runtime stays transport-neutral. Adding WebSocket or gRPC transports
in Phase 2 touches only the adapter layer; no event type changes.

Field shapes track the brief at S29b. Every event carries an
``invocation_id`` (a UUID assigned at ``InvocationStarted``) so
consumers can correlate the stream against the audit chain hashes that
surface on ``InvocationCompleted`` / ``InvocationFailed`` /
``InvariantBlocked``. Iteration-scoped events carry ``iteration_index``
(1-based, consistent with the audit and signal payload conventions
from S27b and S28b).

Cost-bearing events (``IterationCompleted``, ``InvocationCompleted``)
carry ``Decimal`` cost values; the executor sources them from per-LLM
``Completion.cost_usd`` (D88) and accumulates per the D49 / D90 nested
roll-up commitment.

Audit hashes appear on the terminal-event types only: the start-hash
plus end-hash pair on the clean-and-blocked-clean terminations
(``InvocationCompleted``, ``InvariantBlocked``) and a variable-length
``partial_audit_chain_state`` on ``InvocationFailed`` because mid-loop
failures may have emitted zero, one, or two audit rows depending on
where they landed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Union
from uuid import UUID

from contexts.agent.domain.citation_candidates import CitationCandidate
from contexts.agent.domain.termination import TerminationReason
from shared_kernel import TenantContext


@dataclass(frozen=True)
class InvocationStarted:
    """Emitted once at the top of every agent invocation (D90)."""

    invocation_id: UUID
    agent_template_id: UUID
    tenant_context: TenantContext
    model_name: str
    started_at: datetime


@dataclass(frozen=True)
class IterationStarted:
    """Emitted at the start of each LLM-with-tool-loop iteration (D90).

    ``iteration_index`` is 1-based to match the audit and signal payload
    conventions from S27b and S28b (the per-tenant audit row carries
    ``iteration_count`` as a count, not an index; the per-iteration
    span attributes carry the 1-based index for human readability).
    """

    invocation_id: UUID
    iteration_index: int
    started_at: datetime


@dataclass(frozen=True)
class LLMCallStarted:
    """Emitted before the inference adapter is invoked for an iteration (D90).

    ``message_count`` is the length of the conversation passed to the
    inference port; consumers use it to gauge prompt growth across the
    loop (an early signal that the runtime is repeating itself).
    """

    invocation_id: UUID
    iteration_index: int
    model_name: str
    message_count: int
    started_at: datetime


@dataclass(frozen=True)
class ContentDelta:
    """One chunk of assistant content streamed from the inference adapter (D90).

    ``text_fragment`` is the literal substring the model emitted in this
    chunk; consumers concatenate to reconstruct the full content. The
    inference adapter's ``stream_complete`` chunk shape carries the
    delta on every chunk except the terminal one (which carries the
    accumulated tool calls and final cost).
    """

    invocation_id: UUID
    iteration_index: int
    text_fragment: str


@dataclass(frozen=True)
class ToolCallProposed:
    """Emitted when the model proposes a tool call to invoke (D90).

    ``arguments`` is the literal JSON string the model emitted (the
    OpenAI function-calling shape LiteLLM normalises across providers);
    consumers parse if they need structured access. ``classification``
    is the tool's D89 category string (e.g. ``"read_only"``,
    ``"drafting"``); the runtime resolves this from the
    ``ToolDefinitionsLookup`` result composed at ``invoke_agent``.
    """

    invocation_id: UUID
    iteration_index: int
    tool_name: str
    arguments: str
    classification: str


@dataclass(frozen=True)
class ToolCallExecuting:
    """Emitted after the defensive invariant check passes for a tool call (D90).

    Distinct from ``ToolCallProposed`` because the runtime may block the
    proposed call at the invariant boundary per D89 (``InvariantBlocked``
    follows in that path instead of this event).
    """

    invocation_id: UUID
    iteration_index: int
    tool_name: str
    started_at: datetime


@dataclass(frozen=True)
class ToolCallCompleted:
    """Emitted after a tool's invocation returns (D90, D96).

    ``success`` distinguishes ``InvocationOutcome.OK`` from
    ``InvocationOutcome.ERROR`` per the D89 ``ToolInvoker`` contract;
    ``TOOL_NOT_REGISTERED`` and ``INVARIANT_BLOCKED`` outcomes do not
    emit this event because they terminate the loop with their own
    terminal events.

    ``citation_candidates`` carries the attribution surface the tool
    produced per D96. Default empty preserves backwards compatibility
    for tools that produce no citations (Phase 1: only the retrieval
    tool populates it; future tools — web fetch, document parse,
    structured extraction — extend the same field without event-
    vocabulary change). The accumulator at ``invoke_agent`` reads
    this field across the run and passes the deduplicated set to
    ``writer.record_run`` per D96's single-transaction multi-table
    write commitment.
    """

    invocation_id: UUID
    iteration_index: int
    tool_name: str
    success: bool
    result_summary: str
    duration_ms: int
    citation_candidates: tuple[CitationCandidate, ...] = ()


@dataclass(frozen=True)
class IterationCompleted:
    """Emitted at the end of each iteration (D90).

    ``termination_signal`` carries one of: ``"continue"`` (the loop
    continues to the next iteration), ``"content"`` (terminal content
    response from this iteration ends the loop). The terminal-loop
    cases (max-iteration cap, tool-not-registered, invariant-blocked)
    are surfaced via their respective top-level terminal events rather
    than via an iteration-level signal; this event always reflects
    iteration-local progress.
    ``cost_usd`` is the per-iteration cost rolled up across the LLM
    call and any tool calls within the iteration per D90's nested
    cost-roll-up commitment.
    """

    invocation_id: UUID
    iteration_index: int
    termination_signal: str
    duration_ms: int
    cost_usd: Decimal


@dataclass(frozen=True)
class InvocationCompleted:
    """Terminal event for clean termination (D90).

    Carries the canonical ``final_result`` content, the
    ``termination_reason`` from the D88 enum (one of ``CONTENT`` or
    ``MAX_ITERATIONS`` or ``TOOL_NOT_REGISTERED`` or ``ERROR``;
    ``INVARIANT_BLOCKED`` surfaces via ``InvariantBlocked`` instead),
    the rolled-up cost, and the audit-chain start/end hashes per D88.
    """

    invocation_id: UUID
    final_result: str
    termination_reason: TerminationReason
    total_cost_usd: Decimal
    audit_chain_hashes: tuple[str, str]
    duration_ms: int


@dataclass(frozen=True)
class InvocationFailed:
    """Terminal event for unhandled-exception failures (D90).

    ``partial_audit_chain_state`` is variable-length: empty when the
    failure happened before any audit row landed; one hash when only
    the start row landed; two hashes when both rows landed but a
    post-emission exception still bubbled. Consumers should not
    assume a fixed shape.
    """

    invocation_id: UUID
    error_type: str
    error_detail: str
    partial_audit_chain_state: tuple[str, ...]
    duration_ms: int


@dataclass(frozen=True)
class InvariantBlocked:
    """Terminal event for D89 / D82 invariant-block terminations (D90).

    Surfaces the invariant-block path as its own terminal event (rather
    than nesting under ``InvocationCompleted`` with a
    ``TerminationReason.INVARIANT_BLOCKED`` field) because the consumer
    semantics are distinct: an invariant block is a platform-enforced
    safety boundary, not a content/cap/error termination. The runtime
    still emits two audit rows per D26 so ``audit_chain_hashes`` carries
    the start/end pair.
    """

    invocation_id: UUID
    classification: str
    blocked_tool_name: str
    audit_chain_hashes: tuple[str, str]


AgentEvent = Union[
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
]
"""Discriminated union over the eleven event types (D90)."""


TERMINAL_EVENT_TYPES: tuple[type, ...] = (
    InvocationCompleted,
    InvocationFailed,
    InvariantBlocked,
)
"""The three event types that mark the end of an invocation stream (D90).

Consumers use this tuple to detect stream end without enumerating
discriminants by hand. The collect-to-result helper at the application
layer references the same tuple to find the terminal event.
"""


__all__ = [
    "InvocationStarted",
    "IterationStarted",
    "LLMCallStarted",
    "ContentDelta",
    "ToolCallProposed",
    "ToolCallExecuting",
    "ToolCallCompleted",
    "IterationCompleted",
    "InvocationCompleted",
    "InvocationFailed",
    "InvariantBlocked",
    "AgentEvent",
    "TERMINAL_EVENT_TYPES",
]
