"""Model registry — D133's audit-and-future-policy substrate (S47).

D133 commits a model registry as the catalogue Phase 2-A audit-trail
defensibility consumes and Phase 3+ cost-aware routing policies will
consume. Each entry records its model's provider, account, version,
supported operations (structured output, vision, embedding), latency
category, and cost-per-call metadata.

The registry's metadata is recorded for audit and future policy
activation, *not* consumed at routing time at Phase 2-A: tier-to-model
routing resolves through ``InferenceSettings.latency_tier_config``
(per D122) and the LiteLLM gateway routes accordingly. The registry
is data the audit chain and a future Phase 3+ routing-policy adapter
can read; it does not gate which model fires.

Phase 2-A entries:
- ``qwen2.5:7b`` — the pre-S47 default (kept for backward compatibility
  with the existing ``default_model``)
- ``qwen2.5:14b`` — the S47 REAL_TIME_REQUIRED bump per D133/D134
- ``gpt-4o-mini`` — the hosted alternative the operator can select via
  ``INFERENCE_REAL_TIME_REQUIRED_MODEL`` without code change

New entries land at this catalogue when a new model joins the LiteLLM
routing surface; the monthly pricing-review cadence (D41) keeps the
``cost_per_call_*`` fields honest.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class LatencyCategory(StrEnum):
    """Coarse latency descriptor per D133's model-registry shape.

    Distinct from ``LatencyTier`` (D122) — LatencyTier is the *call
    site's* request for a tier; LatencyCategory is the *model's*
    observed latency profile. A future cost-aware routing policy
    consults the category to satisfy the tier within a budget.
    """

    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"


@dataclass(frozen=True)
class ModelRegistryEntry:
    """A single catalogue row per D133."""

    model: str  # the canonical model identifier the gateway accepts
    provider: str  # ollama, openai, anthropic, ...
    account: str  # provider-specific account (D132's account layer)
    version: str  # the version-pinned identifier
    structured_output: bool
    vision: bool
    embedding: bool
    latency_category: LatencyCategory
    input_usd_per_1m_tokens: Decimal
    output_usd_per_1m_tokens: Decimal


MODEL_REGISTRY: dict[str, ModelRegistryEntry] = {
    "qwen2.5:7b": ModelRegistryEntry(
        model="qwen2.5:7b",
        provider="ollama",
        account="default",
        version="qwen2.5:7b",
        structured_output=True,
        vision=False,
        embedding=False,
        latency_category=LatencyCategory.FAST,
        input_usd_per_1m_tokens=Decimal("0"),
        output_usd_per_1m_tokens=Decimal("0"),
    ),
    "qwen2.5:14b": ModelRegistryEntry(
        model="qwen2.5:14b",
        provider="ollama",
        account="default",
        version="qwen2.5:14b",
        structured_output=True,
        vision=False,
        embedding=False,
        latency_category=LatencyCategory.MEDIUM,
        input_usd_per_1m_tokens=Decimal("0"),
        output_usd_per_1m_tokens=Decimal("0"),
    ),
    "gpt-4o-mini": ModelRegistryEntry(
        model="gpt-4o-mini",
        provider="openai",
        account="default",
        version="gpt-4o-mini",
        structured_output=True,
        vision=True,
        embedding=False,
        latency_category=LatencyCategory.FAST,
        input_usd_per_1m_tokens=Decimal("0.150"),
        output_usd_per_1m_tokens=Decimal("0.600"),
    ),
    "nomic-embed-text:v1.5": ModelRegistryEntry(
        model="nomic-embed-text:v1.5",
        provider="ollama",
        account="default",
        version="nomic-embed-text:v1.5",
        structured_output=False,
        vision=False,
        embedding=True,
        latency_category=LatencyCategory.FAST,
        input_usd_per_1m_tokens=Decimal("0"),
        output_usd_per_1m_tokens=Decimal("0"),
    ),
}


__all__ = [
    "LatencyCategory",
    "MODEL_REGISTRY",
    "ModelRegistryEntry",
]
