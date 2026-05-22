"""Unit tests for the latency-tier and four-layer model ontology (S46)."""

from __future__ import annotations

import pytest

from shared_kernel.inference import (
    DEFAULT_ACCOUNT,
    LatencyTier,
    ModelConfiguration,
    ModelIdentifier,
    Provider,
)


def test_latency_tier_values() -> None:
    assert LatencyTier.REAL_TIME_REQUIRED.value == "real_time_required"
    assert LatencyTier.ASYNC_TOLERANT.value == "async_tolerant"


def test_provider_values() -> None:
    assert {p.value for p in Provider} == {"ollama", "anthropic", "openai"}


def test_model_identifier_requires_non_empty_account_and_version() -> None:
    config = ModelConfiguration(latency_tier=LatencyTier.REAL_TIME_REQUIRED)
    with pytest.raises(ValueError, match="account must be non-empty"):
        ModelIdentifier(
            provider=Provider.OLLAMA,
            account="",
            version="qwen2.5:7b",
            configuration=config,
        )
    with pytest.raises(ValueError, match="version must be non-empty"):
        ModelIdentifier(
            provider=Provider.OLLAMA,
            account=DEFAULT_ACCOUNT,
            version="  ",
            configuration=config,
        )


def test_audit_dimensions_carries_four_layers() -> None:
    identifier = ModelIdentifier(
        provider=Provider.OLLAMA,
        account=DEFAULT_ACCOUNT,
        version="qwen2.5:7b",
        configuration=ModelConfiguration(
            latency_tier=LatencyTier.REAL_TIME_REQUIRED,
            temperature=0.0,
            max_tokens=1024,
        ),
    )
    dims = identifier.audit_dimensions()
    assert dims["gen_ai.model.provider"] == "ollama"
    assert dims["gen_ai.model.account"] == "default"
    assert dims["gen_ai.model.version"] == "qwen2.5:7b"
    assert "latency_tier=real_time_required" in dims["gen_ai.model.configuration"]
    assert "temperature=0.0" in dims["gen_ai.model.configuration"]
    assert "max_tokens=1024" in dims["gen_ai.model.configuration"]
    assert (
        "structured_output_schema=none" in dims["gen_ai.model.configuration"]
    )


def test_audit_dimensions_flags_a_present_schema() -> None:
    identifier = ModelIdentifier(
        provider=Provider.OLLAMA,
        account=DEFAULT_ACCOUNT,
        version="qwen2.5:7b",
        configuration=ModelConfiguration(
            latency_tier=LatencyTier.ASYNC_TOLERANT,
            structured_output_schema={"type": "object"},
        ),
    )
    dims = identifier.audit_dimensions()
    assert (
        "structured_output_schema=present"
        in dims["gen_ai.model.configuration"]
    )
    # An unset temperature / max_tokens is simply absent from the
    # composed configuration string.
    assert "temperature=" not in dims["gen_ai.model.configuration"]


def test_model_identifier_is_frozen() -> None:
    identifier = ModelIdentifier(
        provider=Provider.OLLAMA,
        account=DEFAULT_ACCOUNT,
        version="qwen2.5:7b",
        configuration=ModelConfiguration(
            latency_tier=LatencyTier.REAL_TIME_REQUIRED
        ),
    )
    with pytest.raises(Exception):
        identifier.version = "other"  # type: ignore[misc]
