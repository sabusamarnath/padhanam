"""Public read-only query interface for the inference context (D17).

Per D17, every context exposes a single api.py at its root with the
methods other contexts may call. Cross-context callers may import
contexts.inference.api but never contexts.inference.{domain,application,
adapters} — import-linter enforces.

The inference context's surface is request-shaped, not query-shaped:
callers ask for a completion. The port-aware variant (request_completion)
takes the port as a parameter so apps/ can wire the adapter once and pass
through; that single-seam pattern keeps composition out of the context.
"""

from __future__ import annotations

from typing import Sequence

from contexts.inference.application import request_completion as _request_completion
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
    """Run a completion through the supplied InferencePort.

    Thin facade over the application use case so cross-context callers
    have one stable import target.
    """
    return _request_completion(
        port=port,
        messages=messages,
        model=model,
        tenant_id=tenant_id,
    )


__all__ = ["Completion", "Message", "request_completion"]
