"""Unit tests for the LiteLLM four-layer model ontology helpers (S46)."""

from __future__ import annotations

from contexts.inference.adapters.outbound.litellm.model_ontology import (
    litellm_call_kwargs,
    provider_for_model,
    resolve_call_ontology,
)
from padhanam.config import InferenceSettings
from shared_kernel.inference import DEFAULT_ACCOUNT, LatencyTier, Provider


def _settings(**overrides: object) -> InferenceSettings:
    return InferenceSettings(litellm_master_key="test-key", **overrides)


def test_provider_for_model_infers_the_provider() -> None:
    assert provider_for_model("qwen2.5:7b") is Provider.OLLAMA
    assert provider_for_model("gpt-4o-mini") is Provider.OPENAI
    assert provider_for_model("claude-sonnet-4-6") is Provider.ANTHROPIC


def test_resolve_call_ontology_uses_explicit_model() -> None:
    identifier = resolve_call_ontology(
        model="gpt-4o-mini",
        latency_tier=LatencyTier.REAL_TIME_REQUIRED,
        settings=_settings(),
    )
    assert identifier.version == "gpt-4o-mini"
    assert identifier.provider is Provider.OPENAI
    assert identifier.account == DEFAULT_ACCOUNT
    assert identifier.configuration.latency_tier is LatencyTier.REAL_TIME_REQUIRED


def test_resolve_call_ontology_falls_back_to_the_tier_model() -> None:
    # No explicit model — the tier's configured model (here, the
    # default model) resolves the Version layer.
    identifier = resolve_call_ontology(
        model=None,
        latency_tier=LatencyTier.ASYNC_TOLERANT,
        settings=_settings(
            default_model="qwen2.5:7b", async_tolerant_model="claude-sonnet"
        ),
    )
    assert identifier.version == "claude-sonnet"


def test_resolve_call_ontology_folds_structured_output_into_configuration() -> None:
    schema = {"type": "object", "properties": {}}
    identifier = resolve_call_ontology(
        model="qwen2.5:7b",
        latency_tier=LatencyTier.REAL_TIME_REQUIRED,
        settings=_settings(),
        temperature=0.0,
        structured_output_schema=schema,
    )
    assert identifier.configuration.temperature == 0.0
    assert identifier.configuration.structured_output_schema == schema


def test_litellm_call_kwargs_for_a_plain_chat_call() -> None:
    identifier = resolve_call_ontology(
        model="qwen2.5:7b",
        latency_tier=LatencyTier.REAL_TIME_REQUIRED,
        settings=_settings(),
    )
    kwargs = litellm_call_kwargs(identifier, _settings())
    assert kwargs["model"] == "openai/qwen2.5:7b"
    assert kwargs["api_key"] == "test-key"
    assert kwargs["timeout"] == 30.0
    # A plain chat call carries no sampling or structured-output kwargs.
    assert "response_format" not in kwargs
    assert "temperature" not in kwargs


def test_litellm_call_kwargs_maps_the_structured_output_schema() -> None:
    schema = {"type": "object", "properties": {"x": {"type": "string"}}}
    identifier = resolve_call_ontology(
        model="qwen2.5:7b",
        latency_tier=LatencyTier.ASYNC_TOLERANT,
        settings=_settings(),
        temperature=0.2,
        structured_output_schema=schema,
    )
    kwargs = litellm_call_kwargs(identifier, _settings())
    assert kwargs["temperature"] == 0.2
    assert kwargs["timeout"] == 180.0  # the async-tolerant budget
    assert kwargs["response_format"]["type"] == "json_schema"
    assert kwargs["response_format"]["json_schema"]["schema"] == schema
    assert kwargs["response_format"]["json_schema"]["strict"] is True
