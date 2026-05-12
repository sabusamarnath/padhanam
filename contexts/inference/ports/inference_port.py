"""InferencePort — the abstraction the application use case calls.

Adapters (LiteLLM, future provider-direct paths) implement this port.
The shape is narrow: messages, model, tenant_context, optional tools
in; Completion out (for ``complete``) or ``AsyncIterator[CompletionChunk]``
out (for ``stream_complete``). The tenant identity is a full
``TenantContext`` value object from S15 onward (D-entry) rather than a
bare ``tenant_id`` string — adapters that need jurisdiction at request
time (jurisdiction-aware routing) or cost_attribution_id (per-tenant
trace-level cost rollup) read those fields directly without a second
registry lookup at the adapter boundary.

S27b (D88) extends the port for tool-aware chat. ``tools`` defaults to
an empty sequence so every existing call site (plain chat) is
unaffected. The agent runtime passes the role's tool surface (Phase 1:
just the retrieval callable) when invoking the loop; the adapter
forwards to the gateway as the OpenAI function-calling tool list.

S29b (D90) extends the port with ``stream_complete`` for the agent
runtime's streaming pathway. The method name is symmetric with the
existing ``complete`` (verb-first; the streaming-versus-not distinction
is in the verb's prefix) per the S29b pre-write reconciliation. The
non-streaming ``complete`` is preserved for any caller not on the
streaming runtime path (existing inference API consumers, the
``/inference/completions`` HTTP route).

The future orchestration ports (deferred-decisions.md → orchestration
architecture) sit alongside this port; the InferencePort shape stays
compatible with WorkflowExecutor and AgentExecutor invocations because
those orchestrators ultimately call the same use case.
"""

from __future__ import annotations

from typing import AsyncIterator, Protocol, Sequence

from contexts.inference.domain.completion import (
    Completion,
    CompletionChunk,
    Message,
    ToolDefinition,
)
from shared_kernel import TenantContext


class InferencePort(Protocol):
    def complete(
        self,
        messages: Sequence[Message],
        model: str | None,
        tenant_context: TenantContext,
        tools: Sequence[ToolDefinition] = (),
    ) -> Completion: ...

    def stream_complete(
        self,
        messages: Sequence[Message],
        model: str | None,
        tenant_context: TenantContext,
        tools: Sequence[ToolDefinition] = (),
    ) -> AsyncIterator[CompletionChunk]: ...
