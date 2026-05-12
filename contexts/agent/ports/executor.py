"""AgentExecutor port plus invocation DTOs (D88, D90; S27b, S29b).

The ``AgentExecutor`` is the outbound port the ``invoke_agent`` use
case calls to run a single agent invocation. The adapter at
``contexts/agent/adapters/outbound/agent_loop_executor.py`` implements
the hand-rolled LLM-with-tool-loop against the inference context per
D88; future adapters (LangGraph at Phase 2 per D84) implement the same
port without changing the use case.

S29b (D90): the Protocol becomes streaming-only. ``execute(context)``
returns ``AsyncIterator[AgentEvent]`` where the eleven event types live
at ``contexts/agent/domain/events.py``. Non-streaming callers wrap the
stream via the ``collect_to_result`` helper at
``contexts/agent/application/collect.py``. The method name is preserved
(``execute``, not ``invoke``) per the S29b pre-write reconciliation;
only the return shape changes.

``AgentResult`` and ``AgentSignal`` relocate to
``contexts/agent/domain/agent_result.py`` at S29b; this module
re-exports them so existing import paths
(``contexts.agent.ports.executor.AgentResult``, etc.) continue to
work unchanged.

The DTOs in this module are vendor-free per D16 — stdlib dataclasses,
no Pydantic, no provider-specific shapes. The executor adapter
translates to/from the inference context's tool-aware message shape
internally.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator, Mapping, Protocol
from uuid import UUID

from contexts.agent.domain.agent_result import AgentResult, AgentSignal
from contexts.agent.domain.effective_bundle import EffectiveConstraintBundle
from contexts.agent.domain.events import AgentEvent
from contexts.agent.domain.termination import TerminationReason
from contexts.inference.domain.completion import ToolDefinition
from shared_kernel import TenantContext


@dataclass(frozen=True)
class InvocationMessage:
    """One message in an agent's conversation history (D88).

    Phase 1 single-turn invocations leave ``conversation_history``
    empty on ``AgentInvocationContext``; multi-turn history persistence
    defers to Phase 2 per the long-running-agents deferred-decisions
    entry. Defining the DTO now lets the executor's loop construction
    accept the same shape from a future caller without protocol drift.

    The shape is intentionally narrower than the inference context's
    ``Message`` (no tool_calls, no tool_call_id): the agent context's
    conversation history records the user-visible exchange, not the
    inference-side tool-call protocol.
    """

    role: str
    content: str


@dataclass(frozen=True)
class AgentInvocationContext:
    """All state needed to run a single agent invocation (D88).

    Built by ``invoke_agent`` from the resolved agent template, role
    template, and (when methodology lineage is present) the
    methodology's per-role overrides for the agent's specific role.
    Frozen so the executor cannot mutate state during the loop;
    iteration-local state lives inside the executor.

    The lineage fields (``role_template_id``, ``methodology_template_id``,
    ``methodology_version``) feed audit payload composition per D88's
    audit shape; the executor does not need them for the loop itself
    but threads them through to the audit emission step.
    """

    tenant_context: TenantContext
    agent_template_id: UUID
    agent_revision_version: int
    role_template_id: UUID
    role_revision_version: int
    methodology_template_id: UUID | None
    methodology_version: int | None
    effective_bundle: EffectiveConstraintBundle
    user_input: str
    conversation_history: tuple[InvocationMessage, ...] = ()
    # Per D89 commit 5, the LLM-ready ToolDefinition list resolved by
    # ToolDefinitionsLookup at composition time. The executor reads
    # this field when constructing the LiteLLM ``tools`` parameter;
    # the hardcoded retrieval branch from D88 retires. Carried at the
    # ports layer (not on EffectiveConstraintBundle in domain) so the
    # inference context's ToolDefinition type stays out of agent
    # domain per the cross-context independence contract.
    tool_definitions: tuple[ToolDefinition, ...] = ()
    # Per D90 (S29b), the classification per tool keyed by name. The
    # AgentLoopExecutor emits ``ToolCallProposed`` events with the
    # tool's D89 classification ("read_only", "drafting", "user_
    # affecting_with_consent", "financial", "communication", "legal")
    # so consumers (the SSE transport, future CLI / UI) can render
    # tool calls with classification-aware UX. Default empty dict so
    # the executor's existing test scaffolding constructs valid
    # contexts; the wiring adapter populates this from the tools-
    # context invocation service at the same point it resolves
    # ``tool_definitions``. Tools not in the map default to
    # ``"unknown"`` at the executor's emit site.
    tool_classifications: Mapping[str, str] = field(default_factory=dict)


class AgentExecutor(Protocol):
    """The outbound abstraction the ``invoke_agent`` use case calls (D88, D90).

    Streaming-only at S29b per D90: ``execute(context)`` returns an
    ``AsyncIterator[AgentEvent]`` over the eleven event types at
    ``contexts/agent/domain/events.py``. Non-streaming callers wrap the
    stream via ``contexts/agent/application/collect.py``\\'s
    ``collect_to_result`` helper to derive the legacy ``AgentResult``
    shape.

    Adapters implement this Protocol; the use case does not import
    any concrete adapter. The hand-rolled ``AgentLoopExecutor`` adapter
    refactors at S29b commit 5 to yield events; the LangGraph adapter
    defers to Phase 2 per D84 and implements the same streaming shape.
    """

    def execute(
        self, context: AgentInvocationContext
    ) -> AsyncIterator[AgentEvent]: ...


__all__ = [
    "AgentExecutor",
    "AgentInvocationContext",
    "AgentResult",
    "AgentSignal",
    "InvocationMessage",
    "TerminationReason",
]
