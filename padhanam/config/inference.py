from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from padhanam.config.base import PadhanamSettings
from padhanam.config.profiles import Profile, get_profile


class TLSMode(StrEnum):
    PLAINTEXT = "plaintext"
    TLS = "tls"
    MTLS = "mtls"


class InferenceSettings(PadhanamSettings):
    """LiteLLM gateway and model configuration.

    The endpoint, default model, and master key are the values used by
    Padhanam application code (when it lands in S7) and by the smoke-test
    Make targets in S6. The master key has no default: it is a real
    secret and must be supplied via .env, which surfaces a missing
    configuration as a Pydantic validation error rather than a silent
    fall-through.
    """

    litellm_endpoint: str = "http://litellm:4000"
    litellm_master_key: str
    default_model: str = "qwen2.5:7b"
    # S20 / D62: default embedding model. nomic-embed-text:v1.5 served
    # via Ollama, accessed through the LiteLLM gateway at the same
    # endpoint as the chat path. The :v1.5 tag is pinned explicitly
    # rather than ``latest`` so the model card requirements
    # (search_document: corpus prefix, search_query: query prefix,
    # 768-dim native output) hold under upstream Ollama tag drift.
    default_embedding_model: str = "nomic-embed-text:v1.5"
    tls_mode: TLSMode = TLSMode.PLAINTEXT

    @model_validator(mode="after")
    def enforce_prod_tls(self) -> "InferenceSettings":
        # D20: prod profile has no plaintext escape hatch.
        if get_profile() is Profile.PROD and self.tls_mode is TLSMode.PLAINTEXT:
            raise ValueError(
                "InferenceSettings.tls_mode=plaintext is not permitted under "
                "PADHANAM_PROFILE=prod (D20)."
            )
        return self


class ModelPricing(BaseModel):
    """USD-per-1M-token pricing for one model, per D41.

    Pricing is pinned at session-close-time published rates. The monthly
    review cadence in `ops/scheduled_checks.yaml` (D41) catches drift.
    Decimal rather than float so token-to-USD math is reproducible
    independent of platform float behaviour.
    """

    model_config = ConfigDict(frozen=True)

    input_usd_per_1m_tokens: Decimal
    output_usd_per_1m_tokens: Decimal


@dataclass(frozen=True)
class CostBreakdown:
    """Per-call USD cost decomposed into input, output, and total."""

    input_usd: Decimal
    output_usd: Decimal
    total_usd: Decimal


class UnknownModelError(KeyError):
    """Raised when cost lookup is requested for a model not in the table.

    The unknown-model case is a configuration failure — the platform
    must not silently emit zero cost for a real-money model just because
    it was added to LiteLLM's routing without being added to the pricing
    table. Treating it as an error forces the table to stay in sync with
    the routing surface.
    """

    def __init__(self, model: str) -> None:
        super().__init__(model)
        self.model = model


# Pricing table per D41. Reviewed monthly per ops/scheduled_checks.yaml.
# Zero rates are honest for the Ollama-hosted dev model — the call
# carries no per-call vendor cost. Commercial rates are pinned at the
# values vendors published at the session that landed the row; the
# monthly review surfaces drift.
PRICING_TABLE: dict[str, ModelPricing] = {
    "qwen2.5:7b": ModelPricing(
        input_usd_per_1m_tokens=Decimal("0"),
        output_usd_per_1m_tokens=Decimal("0"),
    ),
    "gpt-4o-mini": ModelPricing(
        input_usd_per_1m_tokens=Decimal("0.150"),
        output_usd_per_1m_tokens=Decimal("0.600"),
    ),
    # S20 / D62: nomic-embed-text:v1.5 served via Ollama. Embedding
    # models have only an input dimension (output_tokens=0 by
    # construction), so output_usd_per_1m_tokens stays zero. The dev
    # cost is honest at zero — the call carries no per-call vendor
    # cost. A hosted-embedding row would land here when a hosted
    # default lands; the monthly review (D41) catches drift.
    "nomic-embed-text:v1.5": ModelPricing(
        input_usd_per_1m_tokens=Decimal("0"),
        output_usd_per_1m_tokens=Decimal("0"),
    ),
}


def cost_for(
    model: str,
    input_tokens: int,
    output_tokens: int,
    pricing_table: dict[str, ModelPricing] | None = None,
) -> CostBreakdown:
    """Compute USD cost for a completion against the pricing table.

    Pricing is USD per 1M tokens, so the per-call USD figure is
    ``(tokens / 1_000_000) * usd_per_1m``. Default pricing source is the
    module-level ``PRICING_TABLE``; tests inject a custom dict.
    """
    table = pricing_table if pricing_table is not None else PRICING_TABLE
    pricing = table.get(model)
    if pricing is None:
        raise UnknownModelError(model)

    one_million = Decimal(1_000_000)
    input_usd = (Decimal(input_tokens) / one_million) * pricing.input_usd_per_1m_tokens
    output_usd = (Decimal(output_tokens) / one_million) * pricing.output_usd_per_1m_tokens
    return CostBreakdown(
        input_usd=input_usd,
        output_usd=output_usd,
        total_usd=input_usd + output_usd,
    )
