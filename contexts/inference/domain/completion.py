"""Completion value object — the inference context's domain output.

Vendor-SDK-free by construction: domain code may not import litellm,
langfuse, httpx, or any other adapter-side dependency (D16, enforced
by import-linter). The Completion carries everything callers need to
correlate the response with the trace span the adapter emitted.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Message:
    """One message in a completion request.

    Roles map to the OpenAI chat completion shape (system, user,
    assistant, tool) which is the format the LiteLLM gateway expects.
    Restricting the field to a string keeps the domain framework-free;
    the adapter validates against vendor-supported roles.
    """

    role: str
    content: str


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class Completion:
    """Inference port result.

    `text` is the assistant message content. `model` is the resolved
    model name as the gateway reported it (which may differ from the
    requested name if the gateway routes). `trace_id` lets the caller
    correlate this completion with the OTel span the adapter emitted —
    callers that surface a UI or persist the result use it to deep-link
    to the trace in Langfuse.
    """

    text: str
    model: str
    usage: TokenUsage
    trace_id: str | None = None
    finish_reason: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
