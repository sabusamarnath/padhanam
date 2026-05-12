"""AgentExecutor port plus invocation DTOs (D88, S27b).

The ``AgentExecutor`` is the outbound port the ``invoke_agent`` use
case calls to run a single agent invocation. The adapter at
``contexts/agent/adapters/outbound/agent_loop_executor.py`` implements
the hand-rolled LLM-with-tool-loop against the inference context per
D88; future adapters (LangGraph at Phase 2 per D84) implement the same
port without changing the use case.

The DTOs in this module are vendor-free per D16 — stdlib dataclasses,
no Pydantic, no provider-specific shapes. The executor adapter
translates to/from the inference context's tool-aware message shape
internally.

S27b ships ``execute`` as ``async def``: the underlying LLM call is
sync but bridged via ``asyncio.to_thread`` inside the adapter; the
retrieval client is async; audit emission is async. Matching the
existing async posture of the agent application layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping, Protocol
from uuid import UUID

from contexts.agent.domain.effective_bundle import EffectiveConstraintBundle
from shared_kernel import TenantContext


class TerminationReason(str, Enum):
    """Why an agent invocation stopped (D88).

    Strings rather than opaque ints so audit-row payloads and
    AgentResult instances are human-readable end-to-end. Subclassing
    ``str`` keeps comparison against literal strings ergonomic for
    callers that haven't imported the Enum.
    """

    CONTENT = "content"
    MAX_ITERATIONS = "max_iterations"
    TOOL_NOT_REGISTERED = "tool_not_registered"
    ERROR = "error"


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


@dataclass(frozen=True)
class AgentSignal:
    """A structured signal emitted during an agent invocation (D88).

    Observability surface, not control surface. Phase 1 kinds:
    ``tool_invoked`` (payload carries name, latency_ms, result_summary),
    ``retrieval_performed`` (payload carries query, chunk_count,
    top_score), ``iteration_started`` and ``iteration_completed``
    (payload carries iteration index and per-iteration cost).
    S28b's tool registry extends the kinds; the DTO shape is stable.
    """

    kind: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class AgentResult:
    """Output of a single agent invocation (D88).

    ``cost_total_usd`` is a Decimal to preserve precision; the
    aggregate sums per-LLM-call costs captured via OTel spans tagged
    with ``gen_ai.cost.*`` attributes per D49. The two audit hashes
    (``audit_start_hash``, ``audit_end_hash``) are the
    ``this_event_hash`` values from the AuditEvents emitted at
    invocation start and end per D26; callers can use them to deep-
    link into the audit chain or to verify chain integrity for the
    invocation.

    ``early_termination`` is True when the invocation hit the max-
    iterations cap (D88 conventional 10) or terminated due to an
    unknown-tool branch; False on clean ``content`` termination.
    """

    response_content: str
    signals: tuple[AgentSignal, ...]
    cost_total_usd: Decimal
    iteration_count: int
    termination_reason: TerminationReason
    audit_start_hash: str
    audit_end_hash: str
    early_termination: bool = False
    metadata: dict[str, str] = field(default_factory=dict)


class AgentExecutor(Protocol):
    """The outbound abstraction the ``invoke_agent`` use case calls (D88).

    Adapters implement this Protocol; the use case does not import
    any concrete adapter. The hand-rolled ``AgentLoopExecutor`` lands
    at S27b; the LangGraph adapter defers to Phase 2 per D84.
    """

    async def execute(self, context: AgentInvocationContext) -> AgentResult: ...
