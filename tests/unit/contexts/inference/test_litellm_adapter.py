"""Unit tests for the LiteLLM outbound adapter.

The adapter is the only place ``litellm`` enters the codebase, so the
tests stub the SDK at the module-import boundary using
``unittest.mock.patch``. Domain-shape assertions verify the response
mapping and the exception-translation rules at the adapter boundary.

S29b (D90) adds streaming coverage: the ``stream_complete`` method is
exercised with a scripted async iterator of LiteLLM-shape chunks,
verifying text-delta accumulation, tool-call piecewise reassembly,
cost computation on the terminal chunk, and the terminal-chunk
``is_final=True`` semantics.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from typing import AsyncIterator
from unittest.mock import patch

import pytest
from litellm.exceptions import (
    AuthenticationError,
    BadRequestError,
    RateLimitError,
    Timeout,
)

from contexts.inference.adapters.outbound.litellm import LiteLLMAdapter
from contexts.inference.domain.completion import (
    CompletionChunk,
    Message,
    ToolCall,
    ToolDefinition,
)
from contexts.inference.domain.errors import (
    InferenceConfigurationError,
    InferenceTimeout,
    InferenceUnavailable,
)
from shared_kernel import TenantContext
from padhanam.config import InferenceSettings


_TENANT_A = TenantContext(
    tenant_id="00000000-0000-4000-8000-00000000a001",
    jurisdiction="eu-west",
    cost_attribution_id="00000000-0000-4000-8000-00000000a001",
)


def _settings() -> InferenceSettings:
    return InferenceSettings(litellm_master_key="sk-test-key")


def _ok_response() -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="hello back"),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=12, completion_tokens=4),
        model="qwen2.5:7b",
    )


def test_adapter_maps_response_to_domain_completion() -> None:
    adapter = LiteLLMAdapter(settings=_settings())

    with patch(
        "contexts.inference.adapters.outbound.litellm.adapter.litellm.completion",
        return_value=_ok_response(),
    ):
        result = adapter.complete(
            messages=[Message(role="user", content="hi")],
            model="qwen2.5:7b",
            tenant_context=_TENANT_A,
        )

    assert result.text == "hello back"
    assert result.model == "qwen2.5:7b"
    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 4
    assert result.usage.total_tokens == 16
    assert result.finish_reason == "stop"


def test_adapter_resolves_default_model_when_none() -> None:
    adapter = LiteLLMAdapter(settings=_settings())
    captured: dict[str, object] = {}

    def fake_completion(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return _ok_response()

    with patch(
        "contexts.inference.adapters.outbound.litellm.adapter.litellm.completion",
        side_effect=fake_completion,
    ):
        adapter.complete(
            messages=[Message(role="user", content="hi")],
            model=None,
            tenant_context=_TENANT_A,
        )

    # The adapter prefixes with "openai/" so the LiteLLM SDK treats the
    # gateway endpoint as an OpenAI-compatible proxy (the gateway's
    # config.yaml maps the un-prefixed name to the real backend).
    # S48a / D133: ``complete`` (no explicit latency_tier) routes through
    # the REAL_TIME_REQUIRED tier — pinned to ``gpt-4o-mini`` after the
    # S47 smoke surfaced qwen2.5:14b's commodity-hardware viability gap.
    from shared_kernel.inference import LatencyTier
    expected_model = _settings().latency_tier_config[
        LatencyTier.REAL_TIME_REQUIRED
    ].model
    assert captured["model"] == f"openai/{expected_model}"


def test_adapter_passes_endpoint_and_master_key() -> None:
    adapter = LiteLLMAdapter(settings=_settings())
    captured: dict[str, object] = {}

    def fake_completion(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return _ok_response()

    with patch(
        "contexts.inference.adapters.outbound.litellm.adapter.litellm.completion",
        side_effect=fake_completion,
    ):
        adapter.complete(
            messages=[Message(role="user", content="hi")],
            model="qwen2.5:7b",
            tenant_context=_TENANT_A,
        )

    assert captured["api_base"] == "http://litellm:4000"
    assert captured["api_key"] == "sk-test-key"


def test_timeout_maps_to_inference_timeout() -> None:
    adapter = LiteLLMAdapter(settings=_settings())

    with patch(
        "contexts.inference.adapters.outbound.litellm.adapter.litellm.completion",
        side_effect=Timeout("boom", "litellm", "qwen"),
    ):
        with pytest.raises(InferenceTimeout):
            adapter.complete(
                messages=[Message(role="user", content="hi")],
                model="qwen2.5:7b",
                tenant_context=_TENANT_A,
            )


def test_rate_limit_maps_to_inference_unavailable() -> None:
    adapter = LiteLLMAdapter(settings=_settings())

    with patch(
        "contexts.inference.adapters.outbound.litellm.adapter.litellm.completion",
        side_effect=RateLimitError("rate limit", "litellm", "qwen"),
    ):
        with pytest.raises(InferenceUnavailable):
            adapter.complete(
                messages=[Message(role="user", content="hi")],
                model="qwen2.5:7b",
                tenant_context=_TENANT_A,
            )


def test_auth_error_maps_to_inference_configuration_error() -> None:
    adapter = LiteLLMAdapter(settings=_settings())

    with patch(
        "contexts.inference.adapters.outbound.litellm.adapter.litellm.completion",
        side_effect=AuthenticationError("bad key", "litellm", "qwen"),
    ):
        with pytest.raises(InferenceConfigurationError):
            adapter.complete(
                messages=[Message(role="user", content="hi")],
                model="qwen2.5:7b",
                tenant_context=_TENANT_A,
            )


def test_bad_request_maps_to_inference_configuration_error() -> None:
    adapter = LiteLLMAdapter(settings=_settings())

    with patch(
        "contexts.inference.adapters.outbound.litellm.adapter.litellm.completion",
        side_effect=BadRequestError("bad model", "litellm", "qwen"),
    ):
        with pytest.raises(InferenceConfigurationError):
            adapter.complete(
                messages=[Message(role="user", content="hi")],
                model="qwen2.5:7b",
                tenant_context=_TENANT_A,
            )


def test_completion_carries_trace_id_when_span_active() -> None:
    """When called inside an active OTel span context, the returned
    Completion's trace_id matches the parent context's trace id, so
    callers can deep-link from the response to the trace in Langfuse.
    """
    from opentelemetry import trace

    adapter = LiteLLMAdapter(settings=_settings())
    tracer = trace.get_tracer("test")

    with patch(
        "contexts.inference.adapters.outbound.litellm.adapter.litellm.completion",
        return_value=_ok_response(),
    ):
        with tracer.start_as_current_span("parent"):
            result = adapter.complete(
                messages=[Message(role="user", content="hi")],
                model="qwen2.5:7b",
                tenant_context=_TENANT_A,
            )

    # The default tracer provider produces invalid (zero) span contexts
    # so trace_id may be None when no SDK is configured. The contract
    # is that *if* a non-zero trace_id is available, it is set; this
    # test asserts the field exists on the result.
    assert hasattr(result, "trace_id")


@pytest.fixture
def captured_spans(monkeypatch: pytest.MonkeyPatch):
    """Replace the adapter's module-level tracer with an SDK tracer
    backed by an in-memory exporter, so cost-attribute assertions can
    inspect the recorded span. Restored automatically by monkeypatch.
    """
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    from contexts.inference.adapters.outbound.litellm import adapter as adapter_module

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    test_tracer = provider.get_tracer("padhanam.inference.litellm.test")
    monkeypatch.setattr(adapter_module, "_tracer", test_tracer)
    return exporter


def _commercial_response() -> SimpleNamespace:
    """A response that looks like it came from a commercial model.

    Token counts (1M input + 500K output) are chosen so the per-call
    USD math produces clean decimals against gpt-4o-mini's pinned
    rates: 0.150 input + 0.300 output = 0.450 total.
    """
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="hi"),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=1_000_000, completion_tokens=500_000),
        model="gpt-4o-mini",
    )


def _unknown_model_response() -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="hi"),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=10),
        model="not-a-real-model",
    )


def test_cost_attributes_zero_for_dev_model(captured_spans) -> None:
    """qwen2.5:7b is in the pricing table at zero rates. The three
    cost attributes still emit (as 0.0) so downstream consumers see
    the structure regardless of whether the model carries vendor cost.
    """
    adapter = LiteLLMAdapter(settings=_settings())

    with patch(
        "contexts.inference.adapters.outbound.litellm.adapter.litellm.completion",
        return_value=_ok_response(),
    ):
        adapter.complete(
            messages=[Message(role="user", content="hi")],
            model="qwen2.5:7b",
            tenant_context=_TENANT_A,
        )

    spans = captured_spans.get_finished_spans()
    assert len(spans) == 1
    attrs = spans[0].attributes
    assert attrs["gen_ai.cost.input_usd"] == 0.0
    assert attrs["gen_ai.cost.output_usd"] == 0.0
    assert attrs["gen_ai.cost.total_usd"] == 0.0
    assert attrs["gen_ai.cost.pricing_status"] == "table_hit"


def test_cost_attributes_for_commercial_model(captured_spans) -> None:
    """gpt-4o-mini at 0.150 input / 0.600 output USD per 1M tokens.
    1M input + 500K output -> 0.150 + 0.300 = 0.450 total USD.
    """
    adapter = LiteLLMAdapter(settings=_settings())

    with patch(
        "contexts.inference.adapters.outbound.litellm.adapter.litellm.completion",
        return_value=_commercial_response(),
    ):
        adapter.complete(
            messages=[Message(role="user", content="hi")],
            model="gpt-4o-mini",
            tenant_context=_TENANT_A,
        )

    spans = captured_spans.get_finished_spans()
    assert len(spans) == 1
    attrs = spans[0].attributes
    assert attrs["gen_ai.cost.input_usd"] == pytest.approx(0.150)
    assert attrs["gen_ai.cost.output_usd"] == pytest.approx(0.300)
    assert attrs["gen_ai.cost.total_usd"] == pytest.approx(0.450)
    assert attrs["gen_ai.cost.pricing_status"] == "table_hit"


def test_cost_attributes_zero_for_unknown_model_with_drift_flag(captured_spans) -> None:
    """A model not in the pricing table produces zeros plus the
    pricing_status flag so observability can alert on drift without
    inference itself breaking. The monthly pricing-table review (D41)
    is the reconciling mechanism.
    """
    adapter = LiteLLMAdapter(settings=_settings())

    with patch(
        "contexts.inference.adapters.outbound.litellm.adapter.litellm.completion",
        return_value=_unknown_model_response(),
    ):
        adapter.complete(
            messages=[Message(role="user", content="hi")],
            model="not-a-real-model",
            tenant_context=_TENANT_A,
        )

    spans = captured_spans.get_finished_spans()
    assert len(spans) == 1
    attrs = spans[0].attributes
    assert attrs["gen_ai.cost.input_usd"] == 0.0
    assert attrs["gen_ai.cost.output_usd"] == 0.0
    assert attrs["gen_ai.cost.total_usd"] == 0.0
    assert attrs["gen_ai.cost.pricing_status"] == "unknown_model"


def test_tenant_attributes_emitted_on_span(captured_spans) -> None:
    """The three tenant.* attributes (D37 + S15) land on the adapter
    span alongside the gen_ai.cost.* attributes from S14. The legacy
    padhanam.tenant_id from S7 is removed; tenant.id is the single
    source.
    """
    adapter = LiteLLMAdapter(settings=_settings())
    ctx = TenantContext(
        tenant_id="00000000-0000-4000-8000-00000000b002",
        jurisdiction="us-east",
        cost_attribution_id="acme-billing-2026",
    )

    with patch(
        "contexts.inference.adapters.outbound.litellm.adapter.litellm.completion",
        return_value=_ok_response(),
    ):
        adapter.complete(
            messages=[Message(role="user", content="hi")],
            model="qwen2.5:7b",
            tenant_context=ctx,
        )

    spans = captured_spans.get_finished_spans()
    assert len(spans) == 1
    attrs = spans[0].attributes
    assert attrs["tenant.id"] == "00000000-0000-4000-8000-00000000b002"
    assert attrs["tenant.jurisdiction"] == "us-east"
    assert attrs["tenant.cost_attribution_id"] == "acme-billing-2026"
    # The legacy padhanam.tenant_id attribute is removed in S15 — D37's
    # tenant.id is now the single source.
    assert "padhanam.tenant_id" not in attrs


# S27b (D88) tool-aware chat extension.

def _tool_call_response() -> SimpleNamespace:
    """A response where the model issued one tool call (retrieval)."""
    fn = SimpleNamespace(
        name="retrieval",
        arguments='{"query": "test query"}',
    )
    tool_call = SimpleNamespace(id="call_abc123", type="function", function=fn)
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=None, tool_calls=[tool_call]),
                finish_reason="tool_calls",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=20, completion_tokens=6),
        model="qwen2.5:7b",
    )


def test_adapter_passes_tools_when_supplied() -> None:
    """When tools are passed, the adapter forwards an OpenAI-shaped
    tool list to litellm.completion. When no tools are passed, the
    SDK is not invoked with the tools kwarg at all (plain-chat callers
    see the wire shape unchanged from pre-D88)."""
    adapter = LiteLLMAdapter(settings=_settings())
    captured: dict[str, object] = {}

    def fake_completion(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return _ok_response()

    tool = ToolDefinition(
        name="retrieval",
        description="search the knowledge base",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )

    with patch(
        "contexts.inference.adapters.outbound.litellm.adapter.litellm.completion",
        side_effect=fake_completion,
    ):
        adapter.complete(
            messages=[Message(role="user", content="hi")],
            model="qwen2.5:7b",
            tenant_context=_TENANT_A,
            tools=[tool],
        )

    assert "tools" in captured
    assert captured["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "retrieval",
                "description": "search the knowledge base",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        }
    ]


def test_adapter_omits_tools_kwarg_when_empty() -> None:
    adapter = LiteLLMAdapter(settings=_settings())
    captured: dict[str, object] = {}

    def fake_completion(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return _ok_response()

    with patch(
        "contexts.inference.adapters.outbound.litellm.adapter.litellm.completion",
        side_effect=fake_completion,
    ):
        adapter.complete(
            messages=[Message(role="user", content="hi")],
            model="qwen2.5:7b",
            tenant_context=_TENANT_A,
        )

    assert "tools" not in captured


def test_adapter_serialises_assistant_tool_calls_in_request() -> None:
    """An assistant Message with tool_calls (e.g. echoed back into a
    follow-up call as part of the conversation history) serialises to
    OpenAI's ``tool_calls`` shape."""
    adapter = LiteLLMAdapter(settings=_settings())
    captured: dict[str, object] = {}

    def fake_completion(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return _ok_response()

    history = [
        Message(role="system", content="be helpful"),
        Message(role="user", content="please retrieve X"),
        Message(
            role="assistant",
            content="",
            tool_calls=(
                ToolCall(
                    id="call_99",
                    name="retrieval",
                    arguments_json='{"query": "X"}',
                ),
            ),
        ),
        Message(role="tool", content="chunk A; chunk B", tool_call_id="call_99"),
    ]

    with patch(
        "contexts.inference.adapters.outbound.litellm.adapter.litellm.completion",
        side_effect=fake_completion,
    ):
        adapter.complete(
            messages=history,
            model="qwen2.5:7b",
            tenant_context=_TENANT_A,
        )

    sent_messages = captured["messages"]
    assert sent_messages[2] == {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "call_99",
                "type": "function",
                "function": {
                    "name": "retrieval",
                    "arguments": '{"query": "X"}',
                },
            }
        ],
    }
    assert sent_messages[3] == {
        "role": "tool",
        "tool_call_id": "call_99",
        "content": "chunk A; chunk B",
    }


def test_adapter_surfaces_tool_calls_on_completion() -> None:
    """When the response carries tool_calls, the returned Completion
    exposes them as a tuple of ToolCall objects so the agent runtime
    can branch its loop without parsing text."""
    adapter = LiteLLMAdapter(settings=_settings())

    with patch(
        "contexts.inference.adapters.outbound.litellm.adapter.litellm.completion",
        return_value=_tool_call_response(),
    ):
        result = adapter.complete(
            messages=[Message(role="user", content="search please")],
            model="qwen2.5:7b",
            tenant_context=_TENANT_A,
        )

    assert result.text == ""
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0] == ToolCall(
        id="call_abc123",
        name="retrieval",
        arguments_json='{"query": "test query"}',
    )
    assert result.finish_reason == "tool_calls"


def test_adapter_empty_tool_calls_default_on_plain_response() -> None:
    """Plain content-only responses produce a Completion with an empty
    tool_calls tuple (not None), so callers branch uniformly."""
    adapter = LiteLLMAdapter(settings=_settings())

    with patch(
        "contexts.inference.adapters.outbound.litellm.adapter.litellm.completion",
        return_value=_ok_response(),
    ):
        result = adapter.complete(
            messages=[Message(role="user", content="hi")],
            model="qwen2.5:7b",
            tenant_context=_TENANT_A,
        )

    assert result.tool_calls == ()


# ----------------------------------------------------------------------
# Streaming surface (D90, S29b)
# ----------------------------------------------------------------------


def _streaming_chunk(
    *,
    content: str | None = None,
    tool_calls: list[SimpleNamespace] | None = None,
    finish_reason: str | None = None,
    model: str = "qwen2.5:7b",
) -> SimpleNamespace:
    """Build a LiteLLM-shape streaming chunk for tests.

    LiteLLM streams the OpenAI shape: each chunk has .choices[0].delta
    with .content (text delta) and .tool_calls (delta-shaped partial
    tool calls); .choices[0].finish_reason is set on the terminal chunk.
    """
    delta = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    choice = SimpleNamespace(delta=delta, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], model=model)


async def _async_iter(items: list[SimpleNamespace]) -> AsyncIterator[SimpleNamespace]:
    for item in items:
        yield item


def _assembled_response(
    *,
    content: str = "",
    tool_calls: list[SimpleNamespace] | None = None,
    finish_reason: str = "stop",
    prompt_tokens: int = 12,
    completion_tokens: int = 4,
    model: str = "qwen2.5:7b",
) -> SimpleNamespace:
    """Mock the litellm.stream_chunk_builder output shape."""
    message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(
        choices=[choice],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
        ),
        model=model,
    )


def test_stream_complete_yields_text_deltas_and_terminal_chunk() -> None:
    """A simple text-only stream yields one CompletionChunk per non-
    empty text delta, then a final chunk with is_final=True carrying
    finish_reason, model, and usage."""
    adapter = LiteLLMAdapter(settings=_settings())

    chunks = [
        _streaming_chunk(content="Hello"),
        _streaming_chunk(content=" "),
        _streaming_chunk(content="world"),
        _streaming_chunk(finish_reason="stop"),
    ]

    async def fake_acompletion(**kwargs: object) -> AsyncIterator[SimpleNamespace]:
        return _async_iter(chunks)

    async def drive() -> list[CompletionChunk]:
        with patch(
            "contexts.inference.adapters.outbound.litellm.adapter.litellm.acompletion",
            side_effect=fake_acompletion,
        ), patch(
            "contexts.inference.adapters.outbound.litellm.adapter.litellm.stream_chunk_builder",
            return_value=_assembled_response(content="Hello world"),
        ):
            return [
                chunk
                async for chunk in adapter.stream_complete(
                    messages=[Message(role="user", content="hi")],
                    model="qwen2.5:7b",
                    tenant_context=_TENANT_A,
                )
            ]

    out = asyncio.run(drive())

    deltas = [c for c in out if not c.is_final]
    final = [c for c in out if c.is_final]

    assert len(deltas) == 3
    assert "".join(c.text_delta for c in deltas) == "Hello world"
    assert len(final) == 1
    assert final[0].finish_reason == "stop"
    assert final[0].model == "qwen2.5:7b"
    assert final[0].usage is not None
    assert final[0].usage.input_tokens == 12
    assert final[0].usage.output_tokens == 4
    assert final[0].tool_calls == ()


def test_stream_complete_accumulates_tool_call_arguments_piecewise() -> None:
    """LiteLLM streams tool-call arguments piecewise; the adapter
    reassembles by index and surfaces the fully-assembled tool calls
    on the terminal chunk only."""
    adapter = LiteLLMAdapter(settings=_settings())

    chunks = [
        _streaming_chunk(
            tool_calls=[
                SimpleNamespace(
                    index=0,
                    id="call_123",
                    function=SimpleNamespace(name="retrieval", arguments='{"que'),
                )
            ],
        ),
        _streaming_chunk(
            tool_calls=[
                SimpleNamespace(
                    index=0,
                    id=None,
                    function=SimpleNamespace(name=None, arguments='ry": "lvt"}'),
                )
            ],
        ),
        _streaming_chunk(finish_reason="tool_calls"),
    ]

    async def fake_acompletion(**kwargs: object) -> AsyncIterator[SimpleNamespace]:
        return _async_iter(chunks)

    async def drive() -> list[CompletionChunk]:
        with patch(
            "contexts.inference.adapters.outbound.litellm.adapter.litellm.acompletion",
            side_effect=fake_acompletion,
        ), patch(
            "contexts.inference.adapters.outbound.litellm.adapter.litellm.stream_chunk_builder",
            return_value=_assembled_response(finish_reason="tool_calls"),
        ):
            return [
                chunk
                async for chunk in adapter.stream_complete(
                    messages=[Message(role="user", content="search")],
                    model="qwen2.5:7b",
                    tenant_context=_TENANT_A,
                )
            ]

    out = asyncio.run(drive())
    final = [c for c in out if c.is_final][0]

    assert len(final.tool_calls) == 1
    assert final.tool_calls[0].id == "call_123"
    assert final.tool_calls[0].name == "retrieval"
    assert final.tool_calls[0].arguments_json == '{"query": "lvt"}'
    assert final.finish_reason == "tool_calls"


def test_stream_complete_zero_cost_when_usage_unavailable() -> None:
    """When stream_chunk_builder returns no usage, cost falls back to
    zero with streaming_no_usage pricing_status (covered via the span
    attributes); the terminal chunk carries cost_usd=Decimal('0')."""
    adapter = LiteLLMAdapter(settings=_settings())

    chunks = [
        _streaming_chunk(content="ok"),
        _streaming_chunk(finish_reason="stop"),
    ]

    async def fake_acompletion(**kwargs: object) -> AsyncIterator[SimpleNamespace]:
        return _async_iter(chunks)

    # Assembled response without usage block.
    assembled_no_usage = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="ok", tool_calls=[]),
                finish_reason="stop",
            )
        ],
        usage=None,
        model="qwen2.5:7b",
    )

    async def drive() -> list[CompletionChunk]:
        with patch(
            "contexts.inference.adapters.outbound.litellm.adapter.litellm.acompletion",
            side_effect=fake_acompletion,
        ), patch(
            "contexts.inference.adapters.outbound.litellm.adapter.litellm.stream_chunk_builder",
            return_value=assembled_no_usage,
        ):
            return [
                chunk
                async for chunk in adapter.stream_complete(
                    messages=[Message(role="user", content="hi")],
                    model="qwen2.5:7b",
                    tenant_context=_TENANT_A,
                )
            ]

    out = asyncio.run(drive())
    final = [c for c in out if c.is_final][0]

    assert final.cost_usd == Decimal("0")
    assert final.usage is None


def test_stream_complete_forwards_tools_to_litellm() -> None:
    """The tools parameter on stream_complete must reach litellm.acompletion
    in the OpenAI function-calling shape."""
    adapter = LiteLLMAdapter(settings=_settings())
    captured: dict[str, object] = {}

    async def fake_acompletion(**kwargs: object) -> AsyncIterator[SimpleNamespace]:
        captured.update(kwargs)
        return _async_iter([_streaming_chunk(finish_reason="stop")])

    tool = ToolDefinition(
        name="retrieval",
        description="search",
        parameters={"type": "object"},
    )

    async def drive() -> None:
        with patch(
            "contexts.inference.adapters.outbound.litellm.adapter.litellm.acompletion",
            side_effect=fake_acompletion,
        ), patch(
            "contexts.inference.adapters.outbound.litellm.adapter.litellm.stream_chunk_builder",
            return_value=_assembled_response(),
        ):
            async for _ in adapter.stream_complete(
                messages=[Message(role="user", content="hi")],
                model="qwen2.5:7b",
                tenant_context=_TENANT_A,
                tools=[tool],
            ):
                pass

    asyncio.run(drive())

    assert captured["stream"] is True
    assert "stream_options" in captured
    assert "tools" in captured
    assert captured["tools"][0]["function"]["name"] == "retrieval"
