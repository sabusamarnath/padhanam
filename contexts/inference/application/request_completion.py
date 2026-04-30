"""request_completion use case.

The application layer orchestrates the InferencePort call. Composition
(which adapter implements InferencePort, and any policy or audit
hooks) lives in apps/. The use case stays vendor-free; only the
adapter touches LiteLLM (D16, D27).

The use case is intentionally thin in S7 — there is no model-routing,
budget-checking, or tool-invocation logic yet. Those land alongside
the tenant registry (P3) and orchestration (P5+) without changing the
port signature, which is why the port carries tenant_id from
inception.
"""

from __future__ import annotations

from typing import Sequence

from contexts.inference.domain.completion import Completion, Message
from contexts.inference.ports import InferencePort
from shared_kernel import TenantId


def request_completion(
    *,
    port: InferencePort,
    messages: Sequence[Message],
    model: str | None,
    tenant_id: TenantId,
) -> Completion:
    """Run the completion through the configured InferencePort.

    Side-effects (audit emission, security event on policy denial) are
    composed at the apps/ layer where the port is wired. The use case
    is the single seam the inbound side calls into.
    """
    return port.complete(messages=messages, model=model, tenant_id=tenant_id)
