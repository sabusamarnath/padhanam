"""Four-layer model ontology composition for the LiteLLM adapter (D132, S46).

The D132 four-layer model ontology — Provider, Account, Version,
Configuration — composes here, at the LiteLLM adapter boundary,
rather than at the public inference-port call signature (S46 Finding
C: call sites carry no Provider/Account knowledge, and the
Configuration layer overlaps fields already on the request surface).

This sibling module owns two jobs so ``adapter.py`` stays lean and
under the 800-line ceiling:

- ``resolve_call_ontology`` composes a ``ModelIdentifier`` from the
  resolved model string, the D122 latency tier, and per-call
  configuration. Model resolution is tier-aware — an explicit model
  argument wins, else the per-tier configured model.
- ``litellm_call_kwargs`` maps a composed ``ModelIdentifier`` to the
  base LiteLLM call kwargs (the OpenAI-compatible ``openai/``-prefixed
  model, the gateway endpoint and key, the per-tier timeout, and the
  Configuration-layer sampling and structured-output parameters).

The adapter then captures ``ModelIdentifier.audit_dimensions()`` on
every call's OTel span so the four dimensions are filterable per D132.
"""

from __future__ import annotations

from typing import Any

from padhanam.config import InferenceSettings
from shared_kernel.inference import (
    DEFAULT_ACCOUNT,
    LatencyTier,
    ModelConfiguration,
    ModelIdentifier,
    Provider,
)


def provider_for_model(model: str) -> Provider:
    """Infer the D132 Provider layer from a model identifier string.

    Phase 2-A routes everything through the LiteLLM gateway to local
    Ollama; cloud model identifiers (``gpt-*``, ``claude-*``) map to
    their providers so the audit dimension is correct when a cloud
    model is configured.
    """
    lowered = model.lower()
    if lowered.startswith(("gpt-", "o1", "o3")):
        return Provider.OPENAI
    if lowered.startswith("claude"):
        return Provider.ANTHROPIC
    return Provider.OLLAMA


def resolve_call_ontology(
    *,
    model: str | None,
    latency_tier: LatencyTier,
    settings: InferenceSettings,
    temperature: float | None = None,
    max_tokens: int | None = None,
    structured_output_schema: dict[str, Any] | None = None,
) -> ModelIdentifier:
    """Compose the four-layer ModelIdentifier for one LiteLLM call.

    The Version layer resolves to the explicit ``model`` argument
    when supplied, else the model configured for ``latency_tier`` —
    so an unconfigured deployment routes every tier to ``default_model``
    and only the timeout budget differs. The Account layer is the
    Phase 2-A single-account sentinel.
    """
    resolved_model = model or settings.config_for_tier(latency_tier).model
    return ModelIdentifier(
        provider=provider_for_model(resolved_model),
        account=DEFAULT_ACCOUNT,
        version=resolved_model,
        configuration=ModelConfiguration(
            latency_tier=latency_tier,
            temperature=temperature,
            max_tokens=max_tokens,
            structured_output_schema=structured_output_schema,
        ),
    )


def litellm_call_kwargs(
    identifier: ModelIdentifier, settings: InferenceSettings
) -> dict[str, Any]:
    """Map a composed ModelIdentifier to the base LiteLLM call kwargs.

    The gateway is OpenAI-compatible, so the model carries the
    ``openai/`` prefix. ``timeout`` is the per-tier failure guard
    from D122 configuration. Sampling parameters and the
    structured-output ``response_format`` fold in from the
    Configuration layer only when set, so a plain-chat call produces
    exactly the kwargs the pre-S46 adapter produced plus the timeout.
    """
    config = identifier.configuration
    tier_config = settings.config_for_tier(config.latency_tier)
    kwargs: dict[str, Any] = {
        "model": f"openai/{identifier.version}",
        "api_base": settings.litellm_endpoint,
        "api_key": settings.litellm_master_key,
        "timeout": tier_config.timeout_seconds,
    }
    if config.temperature is not None:
        kwargs["temperature"] = config.temperature
    if config.max_tokens is not None:
        kwargs["max_tokens"] = config.max_tokens
    if config.structured_output_schema is not None:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "structured_output",
                "schema": config.structured_output_schema,
                "strict": True,
            },
        }
    return kwargs


__all__ = [
    "litellm_call_kwargs",
    "provider_for_model",
    "resolve_call_ontology",
]
