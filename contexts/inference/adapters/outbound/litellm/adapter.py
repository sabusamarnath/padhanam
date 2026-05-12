"""LiteLLM outbound adapter implementing InferencePort.

Vendor isolation: this is the only file in the codebase that imports
``litellm``. The import-linter contracts confine the SDK to this
directory; domain and application layers never see the vendor type.

Trace propagation: the adapter wraps each call in an OTel span with
GenAI semantic-convention attributes (D27). The span attaches to the
current OTel context, which the FastAPI instrumentation populates with
the request span — so the trace tree is FastAPI request → inference
port → LiteLLM gateway when the call originates from the API. The
LiteLLM gateway emits its own OTel-native span via OTLP/HTTP to
Langfuse (S6), giving the full request → app → gateway → model tree.

No Langfuse SDK calls live here. The adapter relies on OTel context
propagation: the LiteLLM SDK's underlying httpx call inherits the
current context, the gateway picks up the W3C traceparent header, and
the gateway-emitted span lands as the LLM-call grandchild. D27
portability holds end-to-end.

S27b (D88) extends the adapter for tool-aware chat. ``tools`` (a
sequence of vendor-free ``ToolDefinition``) converts to OpenAI's
function-calling tool list at request time. ``Message`` with
``tool_calls`` (assistant turn) or ``tool_call_id`` (tool turn)
serialises to the OpenAI shape the LiteLLM gateway expects.
Response-side ``tool_calls`` surface on the returned ``Completion``
so the agent runtime can branch its loop. The extension is opt-in:
existing plain-chat callers pass nothing and observe no change in the
wire shape sent to the gateway.
"""

from __future__ import annotations

from typing import Any, Sequence

import litellm
from litellm.exceptions import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from contexts.inference.domain.completion import (
    Completion,
    Message,
    TokenUsage,
    ToolCall,
    ToolDefinition,
)
from contexts.inference.domain.errors import (
    InferenceConfigurationError,
    InferenceError,
    InferenceTimeout,
    InferenceUnavailable,
)
from shared_kernel import TenantContext
from padhanam.config import InferenceSettings, UnknownModelError, cost_for

_tracer = trace.get_tracer("padhanam.inference.litellm")


class LiteLLMAdapter:
    """Implements InferencePort against the LiteLLM OpenAI-compatible gateway.

    Configuration (endpoint, master key, default model) flows through
    InferenceSettings (D19; environment access is centralised in
    padhanam/config/, never scattered across adapters). Each request
    constructs an InferenceSettings instance so configuration changes
    via .env reload between calls without restart.
    """

    def __init__(self, settings: InferenceSettings | None = None) -> None:
        self._settings = settings or InferenceSettings()

    def complete(
        self,
        messages: Sequence[Message],
        model: str | None,
        tenant_context: TenantContext,
        tools: Sequence[ToolDefinition] = (),
    ) -> Completion:
        resolved_model = model or self._settings.default_model
        endpoint = self._settings.litellm_endpoint
        master_key = self._settings.litellm_master_key

        # GenAI semantic conventions per D27. The span name follows the
        # OTel GenAI guidance ("chat {model}") so Langfuse renders it as
        # an LLM-call span rather than an opaque internal span.
        #
        # tenant.* attributes use the Padhanam-domain namespace
        # established by D37 (tenant.id, tenant.jurisdiction). S15
        # extends the namespace with tenant.cost_attribution_id, which
        # joins the same forward-compat shape: if OTel converges on a
        # multi-tenant attribute namespace, the migration is a span-
        # attribute rename here. The legacy padhanam.tenant_id from
        # S7 is removed in this commit — D37's tenant.id is the single
        # source.
        with _tracer.start_as_current_span(
            f"chat {resolved_model}",
            kind=SpanKind.CLIENT,
            attributes={
                "gen_ai.system": "litellm",
                "gen_ai.request.model": resolved_model,
                "gen_ai.operation.name": "chat",
                "tenant.id": tenant_context.tenant_id,
                "tenant.jurisdiction": tenant_context.jurisdiction,
                "tenant.cost_attribution_id": tenant_context.cost_attribution_id,
            },
        ) as span:
            try:
                # Calling the LiteLLM gateway service (S6): the gateway
                # itself is OpenAI-compatible, so we tell the LiteLLM
                # SDK to treat the endpoint as an OpenAI proxy via the
                # `openai/` prefix on the model. The gateway then maps
                # the model name (e.g. "qwen2.5:7b") to its configured
                # backend (Ollama) per ops/litellm/config.yaml.
                call_kwargs: dict[str, Any] = {
                    "model": f"openai/{resolved_model}",
                    "messages": [_message_to_payload(m) for m in messages],
                    "api_base": endpoint,
                    "api_key": master_key,
                }
                if tools:
                    call_kwargs["tools"] = [_tool_to_payload(t) for t in tools]
                response = litellm.completion(**call_kwargs)
            except (Timeout,) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise InferenceTimeout(str(e)) from e
            except (RateLimitError, ServiceUnavailableError, APIConnectionError) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise InferenceUnavailable(str(e)) from e
            except (AuthenticationError, BadRequestError, NotFoundError) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise InferenceConfigurationError(str(e)) from e
            except APIError as e:
                # Catch-all for unmapped LiteLLM errors. The domain shape
                # is preserved; the underlying message stays in __cause__.
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise InferenceError(str(e)) from e

            completion = _completion_from_litellm_response(response, resolved_model)

            span.set_attribute(
                "gen_ai.response.model", completion.model
            )
            span.set_attribute(
                "gen_ai.usage.input_tokens", completion.usage.input_tokens
            )
            span.set_attribute(
                "gen_ai.usage.output_tokens", completion.usage.output_tokens
            )
            if completion.finish_reason is not None:
                span.set_attribute(
                    "gen_ai.response.finish_reasons",
                    [completion.finish_reason],
                )

            # Cost capture per D41. The pricing table at
            # padhanam.config.inference resolves model -> USD rates;
            # cost_for() multiplies token counts by the rates. Cost
            # attributes use Padhanam-domain naming because the OTel
            # GenAI semantic-conventions group has not stabilised cost
            # attribute namespaces as of 2026-05-05; if/when OTel
            # converges on (e.g.) gen_ai.usage.cost.*, the migration
            # is a span-attribute rename here. The dev/Ollama zero-
            # cost case still emits the three cost attributes (as 0.0)
            # so downstream consumers always see the structure. An
            # unknown-model lookup is a configuration-drift signal
            # (a model routed through LiteLLM but missing from the
            # pricing table); the adapter emits zeros plus a
            # gen_ai.cost.pricing_status attribute so the monthly
            # review (D41) and runtime observability can both detect
            # it without breaking inference.
            try:
                breakdown = cost_for(
                    completion.model,
                    completion.usage.input_tokens,
                    completion.usage.output_tokens,
                )
                input_usd = float(breakdown.input_usd)
                output_usd = float(breakdown.output_usd)
                total_usd = float(breakdown.total_usd)
                pricing_status = "table_hit"
            except UnknownModelError:
                input_usd = 0.0
                output_usd = 0.0
                total_usd = 0.0
                pricing_status = "unknown_model"

            span.set_attribute("gen_ai.cost.input_usd", input_usd)
            span.set_attribute("gen_ai.cost.output_usd", output_usd)
            span.set_attribute("gen_ai.cost.total_usd", total_usd)
            span.set_attribute("gen_ai.cost.pricing_status", pricing_status)

            ctx = span.get_span_context()
            trace_id = format(ctx.trace_id, "032x") if ctx.trace_id else None
            return _with_trace_id(completion, trace_id)


def _message_to_payload(m: Message) -> dict[str, Any]:
    """Serialise a domain Message into the LiteLLM/OpenAI request shape.

    - system/user messages: ``{"role", "content"}``.
    - assistant messages with content only: ``{"role", "content"}``.
    - assistant messages with tool_calls: ``{"role", "content", "tool_calls"}``.
    - tool messages: ``{"role", "tool_call_id", "content"}``.
    """
    if m.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": m.tool_call_id or "",
            "content": m.content,
        }
    payload: dict[str, Any] = {"role": m.role, "content": m.content}
    if m.tool_calls:
        payload["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": tc.arguments_json,
                },
            }
            for tc in m.tool_calls
        ]
    return payload


def _tool_to_payload(t: ToolDefinition) -> dict[str, Any]:
    """Serialise a domain ToolDefinition into OpenAI's function-calling shape."""
    return {
        "type": "function",
        "function": {
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
        },
    }


def _tool_calls_from_message(message: Any) -> tuple[ToolCall, ...]:
    """Extract tool_calls (if any) from a LiteLLM response message.

    LiteLLM normalises tool calls to the OpenAI shape: each call carries
    ``id``, ``type="function"``, and ``function`` with ``name`` and
    ``arguments`` (a JSON string). The SDK returns objects or dicts
    depending on the path; ``getattr`` with a dict fallback handles both.
    """
    raw = getattr(message, "tool_calls", None) or []
    out: list[ToolCall] = []
    for tc in raw:
        call_id = getattr(tc, "id", None)
        if call_id is None and isinstance(tc, dict):
            call_id = tc.get("id")
        fn = getattr(tc, "function", None)
        if fn is None and isinstance(tc, dict):
            fn = tc.get("function")
        name = getattr(fn, "name", None)
        if name is None and isinstance(fn, dict):
            name = fn.get("name")
        args = getattr(fn, "arguments", None)
        if args is None and isinstance(fn, dict):
            args = fn.get("arguments")
        out.append(
            ToolCall(
                id=str(call_id or ""),
                name=str(name or ""),
                arguments_json=str(args or "{}"),
            )
        )
    return tuple(out)


def _completion_from_litellm_response(
    response: Any, requested_model: str
) -> Completion:
    """Map a LiteLLM ModelResponse into the domain Completion.

    The LiteLLM SDK returns OpenAI-shaped objects; this function is the
    only place that touches that shape. Every field accessed here has a
    stable place in the OpenAI chat-completion contract LiteLLM honours.
    """
    choice = response.choices[0]
    text = choice.message.content or ""
    finish_reason = getattr(choice, "finish_reason", None)
    usage = response.usage
    input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    response_model = getattr(response, "model", requested_model) or requested_model
    tool_calls = _tool_calls_from_message(choice.message)
    return Completion(
        text=text,
        model=response_model,
        usage=TokenUsage(
            input_tokens=input_tokens, output_tokens=output_tokens
        ),
        finish_reason=finish_reason,
        tool_calls=tool_calls,
    )


def _with_trace_id(completion: Completion, trace_id: str | None) -> Completion:
    if trace_id is None:
        return completion
    return Completion(
        text=completion.text,
        model=completion.model,
        usage=completion.usage,
        trace_id=trace_id,
        finish_reason=completion.finish_reason,
        metadata=completion.metadata,
        tool_calls=completion.tool_calls,
    )
