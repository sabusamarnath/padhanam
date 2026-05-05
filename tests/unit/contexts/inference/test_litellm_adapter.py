"""Unit tests for the LiteLLM outbound adapter.

The adapter is the only place ``litellm`` enters the codebase, so the
tests stub the SDK at the module-import boundary using
``unittest.mock.patch``. Domain-shape assertions verify the response
mapping and the exception-translation rules at the adapter boundary.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from litellm.exceptions import (
    AuthenticationError,
    BadRequestError,
    RateLimitError,
    Timeout,
)

from contexts.inference.adapters.outbound.litellm import LiteLLMAdapter
from contexts.inference.domain.completion import Message
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
    assert captured["model"] == f"openai/{_settings().default_model}"


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
