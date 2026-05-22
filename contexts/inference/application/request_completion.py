"""request_completion use case.

The application layer orchestrates the InferencePort call. Composition
(which adapter implements InferencePort, and any policy or audit
hooks) lives in apps/. The use case stays vendor-free; only the
adapter touches LiteLLM (D16, D27).

The use case is intentionally thin — there is no model-routing,
budget-checking, or tool-invocation logic yet. Those land alongside
orchestration (P5+) without changing the port signature, which is why
the port carries the full ``TenantContext`` from S15 onward (D-entry).

S27b (D88) threads optional ``tools`` through the use case so the
agent runtime can pass a tool definition list. Default empty preserves
plain-chat semantics for every existing caller.
"""

from __future__ import annotations

from typing import Sequence

from contexts.inference.domain.completion import (
    Completion,
    Message,
    ToolDefinition,
)
from contexts.inference.ports import InferencePort
from shared_kernel import LatencyTier, TenantContext


def request_completion(
    *,
    port: InferencePort,
    messages: Sequence[Message],
    model: str | None,
    tenant_context: TenantContext,
    tools: Sequence[ToolDefinition] = (),
    latency_tier: LatencyTier = LatencyTier.REAL_TIME_REQUIRED,
) -> Completion:
    """Run the completion through the configured InferencePort.

    Side-effects (audit emission, security event on policy denial) are
    composed at the apps/ layer where the port is wired. The use case
    is the single seam the inbound side calls into.

    ``latency_tier`` (D122) is defaulted to REAL_TIME_REQUIRED — Path A,
    so existing callers preserve current behaviour; a caller on an
    async-tolerant path passes it explicitly.
    """
    return port.complete(
        messages=messages,
        model=model,
        tenant_context=tenant_context,
        tools=tools,
        latency_tier=latency_tier,
    )
