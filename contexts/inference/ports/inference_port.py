"""InferencePort — the abstraction the application use case calls.

Adapters (LiteLLM, future provider-direct paths) implement this port.
The shape is narrow: messages, model, tenant_context in; Completion
out. The tenant identity is a full ``TenantContext`` value object
from S15 onward (D-entry) rather than a bare ``tenant_id`` string —
adapters that need jurisdiction at request time (jurisdiction-aware
routing) or cost_attribution_id (per-tenant trace-level cost rollup)
read those fields directly without a second registry lookup at the
adapter boundary.

The future orchestration ports (deferred-decisions.md → orchestration
architecture) sit alongside this port; the InferencePort shape stays
compatible with WorkflowExecutor and AgentExecutor invocations because
those orchestrators ultimately call the same use case.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from contexts.inference.domain.completion import Completion, Message
from shared_kernel import TenantContext


class InferencePort(Protocol):
    def complete(
        self,
        messages: Sequence[Message],
        model: str | None,
        tenant_context: TenantContext,
    ) -> Completion: ...
