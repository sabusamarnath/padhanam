"""Unit tests for the D122 latency-tier configuration on InferenceSettings (S46)."""

from __future__ import annotations

from padhanam.config import InferenceSettings, LatencyTierConfig
from shared_kernel.inference import LatencyTier


def test_unconfigured_tiers_resolve_to_the_default_model() -> None:
    """S48a / D133: when the per-tier model fields are explicitly None,
    each tier resolves to ``default_model``. The shipped default
    ``InferenceSettings.real_time_required_model`` is now ``gpt-4o-mini``
    (S48a swap from qwen2.5:14b after the S47 smoke surfaced commodity-
    hardware viability gaps); pass ``None`` here to assert the fallback
    behaviour intact."""
    settings = InferenceSettings(
        litellm_master_key="test-key",
        default_model="qwen2.5:7b",
        real_time_required_model=None,
        async_tolerant_model=None,
    )
    config = settings.latency_tier_config
    assert config[LatencyTier.REAL_TIME_REQUIRED].model == "qwen2.5:7b"
    assert config[LatencyTier.ASYNC_TOLERANT].model == "qwen2.5:7b"


def test_real_time_required_default_pins_to_gpt_4o_mini() -> None:
    """S48a / D133: REAL_TIME_REQUIRED ships pinned to gpt-4o-mini after
    the S47 smoke surfaced qwen2.5:14b's commodity-hardware viability gap
    (progressive 28s→361s slowdown; captures entry 2026-05-26 [S47
    smoke] qwen2.5:14b operator-dogfooding viability on commodity
    hardware). Operator override via ``INFERENCE_REAL_TIME_REQUIRED_MODEL``
    env var remains available — operators without an OpenAI key can
    return to ``qwen2.5:14b`` or ``qwen2.5:7b`` as the local fallback."""
    settings = InferenceSettings(
        litellm_master_key="test-key", default_model="qwen2.5:7b"
    )
    config = settings.latency_tier_config
    assert config[LatencyTier.REAL_TIME_REQUIRED].model == "gpt-4o-mini"
    assert config[LatencyTier.ASYNC_TOLERANT].model == "qwen2.5:7b"


def test_tier_timeout_budgets_differ_by_default() -> None:
    settings = InferenceSettings(litellm_master_key="test-key")
    real_time = settings.config_for_tier(LatencyTier.REAL_TIME_REQUIRED)
    async_tolerant = settings.config_for_tier(LatencyTier.ASYNC_TOLERANT)
    # A real-time call fails fast; an async-tolerant call may run long.
    assert real_time.timeout_seconds < async_tolerant.timeout_seconds


def test_per_tier_model_override() -> None:
    settings = InferenceSettings(
        litellm_master_key="test-key",
        default_model="qwen2.5:7b",
        real_time_required_model="gpt-4o-mini",
        async_tolerant_model="claude-sonnet",
    )
    config = settings.latency_tier_config
    assert config[LatencyTier.REAL_TIME_REQUIRED].model == "gpt-4o-mini"
    assert config[LatencyTier.ASYNC_TOLERANT].model == "claude-sonnet"


def test_config_for_tier_returns_a_latency_tier_config() -> None:
    settings = InferenceSettings(litellm_master_key="test-key")
    resolved = settings.config_for_tier(LatencyTier.REAL_TIME_REQUIRED)
    assert isinstance(resolved, LatencyTierConfig)
    assert resolved.timeout_seconds == 30.0
