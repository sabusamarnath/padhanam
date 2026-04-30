"""InferencePort — the abstraction the application use case calls.

Adapters (LiteLLM, future provider-direct paths) implement this port.
The shape is deliberately narrow: messages, model, tenant_id in;
Completion out. Tenant ID is required from inception per the
jurisdiction principle (principles.md / D12) — a future tenant
registry will resolve tenant_id to per-tenant routing, jurisdiction,
and budget; the port carries the dimension so adding the registry is
configuration, not signature change.

The future orchestration ports (deferred-decisions.md → orchestration
architecture) sit alongside this port; the InferencePort shape stays
compatible with WorkflowExecutor and AgentExecutor invocations because
those orchestrators ultimately call the same use case.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from contexts.inference.domain.completion import Completion, Message
from shared_kernel import TenantId


class InferencePort(Protocol):
    def complete(
        self,
        messages: Sequence[Message],
        model: str | None,
        tenant_id: TenantId,
    ) -> Completion: ...
