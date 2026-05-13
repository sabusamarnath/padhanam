"""ToolInvoker Protocol port + ToolInvocationResult DTO (D89, S28b commit 5).

Consumer-shaped port at the agent context. The ``AgentLoopExecutor``
calls this port for each ``ToolCall`` the LLM issues, receives back
a structured ``ToolInvocationResult`` carrying either the formatted
tool result (the string the executor appends as a ``tool``-role
``Message``), an error message (which the executor surfaces in the
loop's response content), or an invariant-blocked signal (which the
executor translates to ``TerminationReason.INVARIANT_BLOCKED``).

The split between ``ToolDefinitionsLookup`` (read shape) and
``ToolInvoker`` (action shape) is the two-thin-ports pattern per
D89: collapsing them into one ``ToolRegistry`` port would couple the
loop's stability to registry concept evolution. Third reinforcement
of split-by-concern after S26a-1 (MethodologyLookup), S26a-2
(RoleLookup), S27b (AgentRetrievalClient + MethodologyOverridesLookup).

The wiring adapter at ``apps/cli/_cross_context.py`` (commit 7)
implements this port by composing two layers:

1. Tools-context ``check_invocation_admissibility`` — defensive
   classification + invariant check per D89. If blocked, returns the
   ``InvocationOutcome.INVARIANT_BLOCKED`` signal upstream.

2. Tool-specific dispatch — Phase 1 has retrieval as the only
   registered tool, dispatched via ``AgentRetrievalClient`` from
   S27b / D88. Future Phase 2 tools (calendar, email, etc.) plug
   here without changing the agent context's port shape.

The dispatch boundary lives in the wiring adapter rather than the
tools context because retrieval mechanics live in the ingestion
context (behind ``AgentRetrievalClient``); the tools context is the
registry, not the dispatcher. This split keeps the tools context
independent of ingestion per D17.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from contexts.agent.domain.citation_candidates import CitationCandidate
from contexts.inference.domain.completion import ToolCall
from shared_kernel import TenantContext


class InvocationOutcome(str, Enum):
    """Outcome of a single tool invocation (D89)."""

    OK = "ok"
    ERROR = "error"
    INVARIANT_BLOCKED = "invariant_blocked"
    TOOL_NOT_REGISTERED = "tool_not_registered"


@dataclass(frozen=True)
class ToolInvocationResult:
    """Result of one tool invocation at the agent-loop boundary (D89).

    - ``outcome`` carries the structured signal the executor branches
      on. ``OK`` → append ``payload`` as the tool-role message;
      ``ERROR`` → surface ``message`` in the response content;
      ``INVARIANT_BLOCKED`` → terminate with the new
      ``TerminationReason.INVARIANT_BLOCKED`` and append the
      ``payload`` (or ``message``) so audit records what was blocked;
      ``TOOL_NOT_REGISTERED`` → terminate with
      ``TerminationReason.TOOL_NOT_REGISTERED`` (the existing path).
    - ``payload`` is the formatted tool result the executor passes
      back to the LLM verbatim (for ``OK``) or a structured error
      explanation (for non-OK outcomes).
    - ``invariant_index`` is set to 1, 2, or 3 only when ``outcome``
      is ``INVARIANT_BLOCKED``; corresponds to D82's invariant
      numbering per D89's classification-to-invariant mapping
      (financial→1, communication→2, legal→3). The executor surfaces
      this on audit so the chain row carries the named invariant.
    - ``citation_candidates`` carries the attribution surface the
      tool produced per D96. Default empty preserves backwards
      compatibility for tools that produce no citations (Phase 1:
      only the retrieval tool populates it). The executor reads
      this field and copies it onto ``ToolCallCompleted`` for the
      runtime event stream and the ``invoke_agent`` accumulator.
    """

    outcome: InvocationOutcome
    payload: str
    message: str = ""
    invariant_index: int | None = None
    citation_candidates: tuple[CitationCandidate, ...] = ()


class ToolInvoker(Protocol):
    """Dispatch a model-issued tool call and return a structured result.

    Async because the dispatch path may involve async I/O (retrieval
    against per-tenant Postgres, future Phase 2 tools against
    external APIs). The port is intentionally tool-agnostic: the
    wiring adapter at commit 7 routes ``tool_call.name`` (or, after
    a future shape evolution, ``tool_call.tool_id``) to the
    appropriate implementation.
    """

    async def __call__(
        self,
        *,
        tool_call: ToolCall,
        tenant_context: TenantContext,
    ) -> ToolInvocationResult:
        ...
