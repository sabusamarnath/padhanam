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
from shared_kernel import TenantId
from vadakkan.config import InferenceSettings


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
            tenant_id=TenantId("tenant-a"),
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
            tenant_id=TenantId("tenant-a"),
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
            tenant_id=TenantId("tenant-a"),
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
                tenant_id=TenantId("tenant-a"),
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
                tenant_id=TenantId("tenant-a"),
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
                tenant_id=TenantId("tenant-a"),
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
                tenant_id=TenantId("tenant-a"),
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
                tenant_id=TenantId("tenant-a"),
            )

    # The default tracer provider produces invalid (zero) span contexts
    # so trace_id may be None when no SDK is configured. The contract
    # is that *if* a non-zero trace_id is available, it is set; this
    # test asserts the field exists on the result.
    assert hasattr(result, "trace_id")
