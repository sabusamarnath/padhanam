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

import json
from decimal import Decimal
from typing import Any, AsyncIterator, Sequence

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
    CompletionChunk,
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
from shared_kernel.structured_output import (
    StructuredOutputRequest,
    StructuredOutputResponse,
)
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
                cost_decimal = breakdown.total_usd
                pricing_status = "table_hit"
            except UnknownModelError:
                input_usd = 0.0
                output_usd = 0.0
                total_usd = 0.0
                cost_decimal = Decimal("0")
                pricing_status = "unknown_model"

            span.set_attribute("gen_ai.cost.input_usd", input_usd)
            span.set_attribute("gen_ai.cost.output_usd", output_usd)
            span.set_attribute("gen_ai.cost.total_usd", total_usd)
            span.set_attribute("gen_ai.cost.pricing_status", pricing_status)

            ctx = span.get_span_context()
            trace_id = format(ctx.trace_id, "032x") if ctx.trace_id else None
            return _with_cost_and_trace(completion, trace_id, cost_decimal)

    async def stream_complete(
        self,
        messages: Sequence[Message],
        model: str | None,
        tenant_context: TenantContext,
        tools: Sequence[ToolDefinition] = (),
    ) -> AsyncIterator[CompletionChunk]:
        """Streaming completion against the LiteLLM gateway (D90, S29b).

        Calls ``litellm.acompletion(..., stream=True)`` for the async-
        streaming path; translates each LiteLLM chunk into a domain-
        shape ``CompletionChunk``; accumulates tool calls across deltas
        (LiteLLM emits tool-call arguments piecewise per the OpenAI
        function-calling streaming shape); reassembles all chunks via
        ``litellm.stream_chunk_builder`` at stream end to compute final
        usage and cost; emits a terminal chunk with ``is_final=True``
        carrying the resolved model name, finish reason, cost, and the
        fully-assembled tool calls.

        Trace span: one ``chat {model}`` span wraps the whole stream
        (kind=CLIENT), matching the existing ``complete`` adapter's
        span shape so the LiteLLM-side and Padhanam-side spans nest
        consistently regardless of which method initiated the call.
        Intermediate chunks do not get their own spans (one chunk-per-
        span would explode the trace tree without consumer evidence);
        the gateway-emitted span tree per D27 propagation gives chunk-
        level visibility when needed.

        Cost capture per D49: usage tokens reassemble via
        stream_chunk_builder; cost_for() then maps to USD. The dev/
        Ollama zero-cost case and the unknown-model-pricing case both
        surface as Decimal("0") with the appropriate pricing_status
        attribute on the span. If stream_chunk_builder fails to produce
        usage (some streaming providers omit the usage block entirely),
        the cost falls back to Decimal("0") with a
        ``streaming_no_usage`` pricing_status flag distinct from
        ``unknown_model``.
        """
        resolved_model = model or self._settings.default_model
        endpoint = self._settings.litellm_endpoint
        master_key = self._settings.litellm_master_key

        with _tracer.start_as_current_span(
            f"chat {resolved_model}",
            kind=SpanKind.CLIENT,
            attributes={
                "gen_ai.system": "litellm",
                "gen_ai.request.model": resolved_model,
                "gen_ai.operation.name": "chat",
                "gen_ai.request.streaming": True,
                "tenant.id": tenant_context.tenant_id,
                "tenant.jurisdiction": tenant_context.jurisdiction,
                "tenant.cost_attribution_id": tenant_context.cost_attribution_id,
            },
        ) as span:
            call_kwargs: dict[str, Any] = {
                "model": f"openai/{resolved_model}",
                "messages": [_message_to_payload(m) for m in messages],
                "api_base": endpoint,
                "api_key": master_key,
                "stream": True,
                # Ask providers that support it (cloud OpenAI-compatible
                # gateways) to include usage on the terminal chunk so
                # cost_for() can compute on the same span. Dev / Ollama
                # may ignore the option; stream_chunk_builder reassembles
                # tokens as a fallback either way.
                "stream_options": {"include_usage": True},
            }
            if tools:
                call_kwargs["tools"] = [_tool_to_payload(t) for t in tools]

            try:
                response_iter = await litellm.acompletion(**call_kwargs)
            except (Timeout,) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise InferenceTimeout(str(e)) from e
            except (
                RateLimitError,
                ServiceUnavailableError,
                APIConnectionError,
            ) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise InferenceUnavailable(str(e)) from e
            except (AuthenticationError, BadRequestError, NotFoundError) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise InferenceConfigurationError(str(e)) from e
            except APIError as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise InferenceError(str(e)) from e

            # Tool-call accumulator: LiteLLM streams tool calls
            # piecewise; each delta's tool_calls entry has an ``index``
            # field and partial fields. We accumulate by index so the
            # terminal chunk can surface the fully-assembled list.
            tool_call_accumulator: dict[int, dict[str, Any]] = {}
            raw_chunks: list[Any] = []
            finish_reason: str | None = None
            response_model_observed: str | None = None

            try:
                async for raw_chunk in response_iter:
                    raw_chunks.append(raw_chunk)
                    response_model_observed = (
                        getattr(raw_chunk, "model", None)
                        or response_model_observed
                    )
                    choices = getattr(raw_chunk, "choices", None) or []
                    if not choices:
                        continue
                    choice = choices[0]
                    finish_reason = (
                        getattr(choice, "finish_reason", None) or finish_reason
                    )
                    delta = getattr(choice, "delta", None)
                    if delta is None:
                        continue
                    text_delta = getattr(delta, "content", None) or ""
                    delta_tool_calls = getattr(delta, "tool_calls", None) or []
                    _accumulate_tool_call_deltas(
                        tool_call_accumulator, delta_tool_calls
                    )

                    if text_delta:
                        yield CompletionChunk(
                            text_delta=text_delta,
                            is_final=False,
                        )
            except (Timeout,) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise InferenceTimeout(str(e)) from e
            except (
                RateLimitError,
                ServiceUnavailableError,
                APIConnectionError,
            ) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise InferenceUnavailable(str(e)) from e
            except APIError as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise InferenceError(str(e)) from e

            # Reassemble the full response so we can extract usage and
            # cost on the terminal chunk. stream_chunk_builder returns
            # the same shape as a non-streaming completion.
            usage: TokenUsage | None = None
            cost_decimal = Decimal("0")
            pricing_status = "streaming_no_usage"

            try:
                assembled = litellm.stream_chunk_builder(raw_chunks)
            except Exception:  # noqa: BLE001 — vendor-side reassembly failure
                assembled = None

            response_model = response_model_observed or resolved_model

            if assembled is not None:
                response_model = (
                    getattr(assembled, "model", None) or response_model
                )
                usage_raw = getattr(assembled, "usage", None)
                if usage_raw is not None:
                    input_tokens = int(
                        getattr(usage_raw, "prompt_tokens", 0) or 0
                    )
                    output_tokens = int(
                        getattr(usage_raw, "completion_tokens", 0) or 0
                    )
                    if input_tokens or output_tokens:
                        usage = TokenUsage(
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                        )
                        try:
                            breakdown = cost_for(
                                response_model, input_tokens, output_tokens
                            )
                            cost_decimal = breakdown.total_usd
                            pricing_status = "table_hit"
                        except UnknownModelError:
                            cost_decimal = Decimal("0")
                            pricing_status = "unknown_model"

            span.set_attribute("gen_ai.response.model", response_model)
            if usage is not None:
                span.set_attribute(
                    "gen_ai.usage.input_tokens", usage.input_tokens
                )
                span.set_attribute(
                    "gen_ai.usage.output_tokens", usage.output_tokens
                )
            span.set_attribute(
                "gen_ai.cost.input_usd",
                float(cost_for_input(usage, response_model)),
            )
            span.set_attribute(
                "gen_ai.cost.output_usd",
                float(cost_for_output(usage, response_model)),
            )
            span.set_attribute("gen_ai.cost.total_usd", float(cost_decimal))
            span.set_attribute("gen_ai.cost.pricing_status", pricing_status)
            if finish_reason is not None:
                span.set_attribute(
                    "gen_ai.response.finish_reasons", [finish_reason]
                )

            ctx = span.get_span_context()
            trace_id = format(ctx.trace_id, "032x") if ctx.trace_id else None

            yield CompletionChunk(
                text_delta="",
                is_final=True,
                finish_reason=finish_reason,
                model=response_model,
                tool_calls=_finalize_tool_calls(tool_call_accumulator),
                usage=usage,
                cost_usd=cost_decimal,
                trace_id=trace_id,
            )

    async def generate_structured(
        self, request: StructuredOutputRequest
    ) -> StructuredOutputResponse[dict[str, Any]]:
        """Structured-output completion against the LiteLLM gateway (D130, S45).

        Implements ``StructuredOutputPort`` additively — the existing
        ``complete`` / ``stream_complete`` surface is unchanged. The
        request's JSON Schema ``dict`` maps to LiteLLM's
        ``response_format`` ``json_schema`` form; the gateway returns a
        JSON object which the adapter parses into the response value.

        The schema representation is settled here per D130: the
        vendor-neutral JSON Schema dict at the ``shared_kernel``
        primitive maps to the ``{"type": "json_schema", "json_schema":
        {...}}`` shape LiteLLM forwards as the OpenAI-compatible
        structured-output parameter.

        ``StructuredOutputPort.generate_structured`` carries no
        TenantContext, so this span omits the ``tenant.*`` attributes
        and per-tenant cost attribution that ``complete`` emits — no
        Phase 2-A surface consumes structured output (the first
        consumers land at P14), and the port extends with a tenant
        parameter at that point if attribution is required.
        """
        resolved_model = request.model_hint or self._settings.default_model
        endpoint = self._settings.litellm_endpoint
        master_key = self._settings.litellm_master_key

        with _tracer.start_as_current_span(
            f"structured_output {resolved_model}",
            kind=SpanKind.CLIENT,
            attributes={
                "gen_ai.system": "litellm",
                "gen_ai.request.model": resolved_model,
                "gen_ai.operation.name": "structured_output",
            },
        ) as span:
            call_kwargs: dict[str, Any] = {
                "model": f"openai/{resolved_model}",
                "messages": [
                    {"role": "user", "content": request.prompt}
                ],
                "api_base": endpoint,
                "api_key": master_key,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "structured_output",
                        "schema": request.schema,
                        "strict": True,
                    },
                },
            }
            if request.temperature is not None:
                call_kwargs["temperature"] = request.temperature

            try:
                response = await litellm.acompletion(**call_kwargs)
            except (Timeout,) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise InferenceTimeout(str(e)) from e
            except (
                RateLimitError,
                ServiceUnavailableError,
                APIConnectionError,
            ) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise InferenceUnavailable(str(e)) from e
            except (
                AuthenticationError,
                BadRequestError,
                NotFoundError,
            ) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise InferenceConfigurationError(str(e)) from e
            except APIError as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise InferenceError(str(e)) from e

            choice = response.choices[0]
            content = choice.message.content or "{}"
            try:
                parsed = json.loads(content)
            except (ValueError, TypeError) as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise InferenceError(
                    f"structured output was not valid JSON: {e}"
                ) from e
            if not isinstance(parsed, dict):
                raise InferenceError(
                    "structured output must be a JSON object; got "
                    f"{type(parsed).__name__}"
                )

            response_model = (
                getattr(response, "model", None) or resolved_model
            )
            usage = getattr(response, "usage", None)
            input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
            finish_reason = getattr(choice, "finish_reason", None)

            span.set_attribute("gen_ai.response.model", response_model)
            span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
            span.set_attribute("gen_ai.usage.output_tokens", output_tokens)

            return StructuredOutputResponse(
                value=parsed,
                confidence=_confidence_from_value(parsed),
                provider_metadata={
                    "model": response_model,
                    "finish_reason": finish_reason,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                },
            )


def _confidence_from_value(value: dict[str, Any]) -> float | None:
    """Lift a top-level numeric ``confidence`` field, per D130.

    D130: a structured-output response's ``confidence`` is null unless
    the request schema itself carries a confidence field. When the
    parsed value carries a numeric top-level ``confidence``, surface
    it on the response; otherwise the response's confidence is None.
    """
    raw = value.get("confidence")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    return None


def _accumulate_tool_call_deltas(
    accumulator: dict[int, dict[str, Any]],
    delta_tool_calls: list[Any],
) -> None:
    """Merge tool-call deltas into the index-keyed accumulator.

    LiteLLM streams tool calls in the OpenAI shape: each delta's
    ``tool_calls`` is a list of entries with ``index`` plus partial
    fields. The first delta for a given index carries ``id`` and
    ``function.name``; subsequent deltas extend ``function.arguments``
    fragment-by-fragment. The accumulator keys by index and concatenates
    arguments fragments.
    """
    for tc in delta_tool_calls:
        index = getattr(tc, "index", None)
        if index is None and isinstance(tc, dict):
            index = tc.get("index")
        if index is None:
            continue
        bucket = accumulator.setdefault(int(index), {"arguments_parts": []})
        tc_id = getattr(tc, "id", None) or (
            tc.get("id") if isinstance(tc, dict) else None
        )
        if tc_id:
            bucket["id"] = str(tc_id)
        fn = getattr(tc, "function", None) or (
            tc.get("function") if isinstance(tc, dict) else None
        )
        if fn is not None:
            name = getattr(fn, "name", None) or (
                fn.get("name") if isinstance(fn, dict) else None
            )
            if name:
                bucket["name"] = str(name)
            args_fragment = getattr(fn, "arguments", None) or (
                fn.get("arguments") if isinstance(fn, dict) else None
            )
            if args_fragment:
                bucket["arguments_parts"].append(str(args_fragment))


def _finalize_tool_calls(
    accumulator: dict[int, dict[str, Any]],
) -> tuple[ToolCall, ...]:
    """Convert the index-keyed accumulator into a frozen ToolCall tuple."""
    out: list[ToolCall] = []
    for index in sorted(accumulator.keys()):
        bucket = accumulator[index]
        out.append(
            ToolCall(
                id=str(bucket.get("id", "")),
                name=str(bucket.get("name", "")),
                arguments_json="".join(bucket.get("arguments_parts", []))
                or "{}",
            )
        )
    return tuple(out)


def cost_for_input(usage: TokenUsage | None, model: str) -> Decimal:
    """Compute input-side cost component; zero when usage unavailable."""
    if usage is None:
        return Decimal("0")
    try:
        return cost_for(model, usage.input_tokens, 0).total_usd
    except UnknownModelError:
        return Decimal("0")


def cost_for_output(usage: TokenUsage | None, model: str) -> Decimal:
    """Compute output-side cost component; zero when usage unavailable."""
    if usage is None:
        return Decimal("0")
    try:
        return cost_for(model, 0, usage.output_tokens).total_usd
    except UnknownModelError:
        return Decimal("0")


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


def _with_cost_and_trace(
    completion: Completion,
    trace_id: str | None,
    cost_usd: Decimal,
) -> Completion:
    """Return a new Completion enriched with trace_id and cost_usd.

    Both are adapter-derived (trace_id from the open OTel span context;
    cost_usd from the pricing-table lookup) so they land here rather
    than on the initial Completion construction in
    ``_completion_from_litellm_response``.
    """
    return Completion(
        text=completion.text,
        model=completion.model,
        usage=completion.usage,
        trace_id=trace_id,
        finish_reason=completion.finish_reason,
        metadata=completion.metadata,
        tool_calls=completion.tool_calls,
        cost_usd=cost_usd,
    )
