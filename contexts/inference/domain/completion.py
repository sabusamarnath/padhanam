"""Completion value object — the inference context's domain output.

Vendor-SDK-free by construction: domain code may not import litellm,
langfuse, httpx, or any other adapter-side dependency (D16, enforced
by import-linter). The Completion carries everything callers need to
correlate the response with the trace span the adapter emitted.

S27b (D88) extends the shape for tool-aware chat. ``ToolCall`` and
``ToolDefinition`` are the vendor-free shapes the agent runtime
exchanges with the model through the adapter. ``Message`` gains an
optional ``tool_calls`` field (assistant turn returning model-issued
calls) and a ``tool_call_id`` field (tool-role turn carrying the
result of a previous call). ``Completion`` gains a top-level
``tool_calls`` field surfaced from the model's response so the agent
runtime can branch its loop without parsing the text. The OpenAI
function-calling shape LiteLLM normalises across providers maps
cleanly to these fields; the adapter is the only file that knows the
gateway-side wire shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    """A model-issued call to a named tool with JSON-encoded arguments (D88).

    ``id`` is the call identifier the model produced (echoed back on
    the tool-role message that carries the result). ``name`` is the
    tool's opaque string identifier; the inference layer does not
    resolve it. ``arguments_json`` is the literal JSON string the
    model emitted (the OpenAI function-calling shape LiteLLM
    normalises across providers); the agent runtime parses it.
    """

    id: str
    name: str
    arguments_json: str


@dataclass(frozen=True)
class ToolDefinition:
    """A vendor-free description of a tool the model may call (D88).

    The adapter converts to the gateway's expected shape (LiteLLM
    uses OpenAI's function-calling format). ``parameters`` is a
    JSON-schema payload describing the tool's argument shape; the
    domain treats it as an opaque dict per the existing convention
    for ``retrieval_strategy`` and ``filter_tree`` (``Mapping[str, Any]``).
    """

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class Message:
    """One message in a completion request.

    Roles map to the OpenAI chat completion shape (system, user,
    assistant, tool) which is the format the LiteLLM gateway expects.
    Restricting the field to a string keeps the domain framework-free;
    the adapter validates against vendor-supported roles.

    Per D88, assistant messages may carry ``tool_calls`` (an empty
    tuple when the message is plain content). Tool-role messages
    carry ``tool_call_id`` matching the assistant's prior call. Plain
    system, user, and content-only assistant messages leave both
    fields at their defaults.
    """

    role: str
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None


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

    Per D88, ``tool_calls`` surfaces model-issued tool calls when the
    response triggered them; empty tuple otherwise. The agent runtime
    branches its loop on this field (content-only terminates;
    tool_calls continues into the tool-execution branch).
    """

    text: str
    model: str
    usage: TokenUsage
    trace_id: str | None = None
    finish_reason: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    tool_calls: tuple[ToolCall, ...] = ()
    # Per D88, the adapter surfaces per-call cost on Completion so the
    # agent runtime can aggregate per-invocation cost without OTel-span
    # introspection. Default Decimal("0") covers the unknown-model
    # (pricing-status drift) and dev-zero-cost paths uniformly.
    cost_usd: Decimal = field(default_factory=lambda: Decimal("0"))


@dataclass(frozen=True)
class CompletionChunk:
    """One chunk from a streaming completion (D90, S29b).

    The streaming InferencePort yields these chunks as an
    ``AsyncIterator[CompletionChunk]``. Intermediate chunks carry
    ``text_delta`` (the model's incremental output) and partial
    tool-call state; the terminal chunk (``is_final=True``) carries
    the resolved model name, final cost, finish reason, and any
    final ``Completion``-equivalent fields the caller needs.

    Tool calls accumulate across chunks because LiteLLM (matching
    OpenAI's function-calling streaming shape) emits tool-call arguments
    piecewise — first chunk carries the call id and function name,
    subsequent chunks add fragments to ``function.arguments``. The
    adapter accumulates inside its loop and emits the fully-assembled
    ``tool_calls`` tuple on the terminal chunk; intermediate chunks
    carry an empty tuple to keep the chunk shape unambiguous.

    Per the vendor-isolation principle (D4 / D27 / D90), this shape
    is the only contract callers and consumers see; the LiteLLM-side
    StreamingChunk type stays inside the adapter.
    """

    text_delta: str
    is_final: bool = False
    finish_reason: str | None = None
    model: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    usage: TokenUsage | None = None
    cost_usd: Decimal = field(default_factory=lambda: Decimal("0"))
    trace_id: str | None = None
