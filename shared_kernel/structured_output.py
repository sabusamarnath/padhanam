"""Structured-output discipline — cross-cutting LLM-call primitive (D130, S45).

D130 commits structured output as a cross-cutting discipline at the
LLM-call boundary: a request, a generic response, and a port for
LLM calls that must return a schema-conforming structured value
rather than free text. It is not a bounded context — it is a
value-object-plus-Protocol shape that every per-context
structured-output consumer conforms to.

``StructuredOutputRequest.schema`` is a JSON Schema object held as a
plain ``dict``. The dict is vendor-neutral and framework-free,
which ``shared_kernel/`` requires — Pydantic is forbidden here by
the ``shared-kernel-policed`` import-linter contract per D16. The
LiteLLM adapter (S45 commit 9) maps the JSON Schema dict to the
vendor's ``response_format`` parameter.

``StructuredOutputResponse[T]`` is generic over the parsed value
type so a context can hold a typed response after conversion;
``StructuredOutputPort`` returns ``StructuredOutputResponse[dict[str, Any]]``
— the parsed JSON object. The inference adapter implements the port
additively at S45 per D130.

D131 builds on this primitive: provenance-aware response composition
treats citation fields in the ``schema`` as a load-bearing
requirement, not an optional affordance.

Framework-free per D16 — shared_kernel is policed; stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

from shared_kernel.inference import LatencyTier

T = TypeVar("T")


@dataclass(frozen=True)
class StructuredOutputRequest:
    """A request for a schema-conforming structured LLM response.

    ``schema`` is a JSON Schema object (a plain ``dict``).
    ``latency_tier`` is the D122 routing hint — defaulted to
    ``REAL_TIME_REQUIRED`` (Path A, S46) so existing callers preserve
    current behaviour; a user-invoked surface like the manual entry
    cell passes it explicitly. ``temperature`` and ``model_hint`` are
    optional; an unset ``model_hint`` lets the adapter resolve its
    default model.
    """

    prompt: str
    schema: dict[str, Any]
    latency_tier: LatencyTier = LatencyTier.REAL_TIME_REQUIRED
    temperature: float | None = None
    model_hint: str | None = None

    def __post_init__(self) -> None:
        if not self.prompt or not self.prompt.strip():
            raise ValueError("StructuredOutputRequest.prompt must be non-empty")
        if not self.schema:
            raise ValueError("StructuredOutputRequest.schema must be non-empty")


@dataclass(frozen=True)
class StructuredOutputResponse(Generic[T]):
    """A schema-conforming structured LLM response.

    ``value`` is the parsed schema-conforming result. ``confidence``
    is an optional self-reported confidence — null unless the schema
    itself carries a confidence field. ``provider_metadata`` carries
    model name, token usage, and finish reason.
    """

    value: T
    confidence: float | None
    provider_metadata: dict[str, Any]


@runtime_checkable
class StructuredOutputPort(Protocol):
    """The structured-output abstraction at the LLM-call boundary.

    An adapter satisfies ``StructuredOutputPort`` structurally — the
    inference LiteLLM adapter implements it additively at S45. The
    ``@runtime_checkable`` decorator allows ``isinstance`` conformance
    checks, which the contract harness exercises.
    """

    async def generate_structured(
        self, request: StructuredOutputRequest
    ) -> StructuredOutputResponse[dict[str, Any]]:
        """Return a schema-conforming structured response."""
        ...


__all__ = [
    "StructuredOutputPort",
    "StructuredOutputRequest",
    "StructuredOutputResponse",
]
