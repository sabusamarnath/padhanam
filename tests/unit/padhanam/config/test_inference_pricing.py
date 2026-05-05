"""Unit tests for the pricing table at padhanam.config.inference.

The pricing table is the configuration source for D41's cost-capture
commitment. These tests cover the table-lookup happy path against the
two pinned models, the missing-model error path, and the zero-cost
case for the dev model.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from padhanam.config import (
    PRICING_TABLE,
    CostBreakdown,
    ModelPricing,
    UnknownModelError,
    cost_for,
)


def test_pricing_table_includes_dev_model_at_zero_rates() -> None:
    pricing = PRICING_TABLE["qwen2.5:7b"]
    assert pricing.input_usd_per_1m_tokens == Decimal("0")
    assert pricing.output_usd_per_1m_tokens == Decimal("0")


def test_pricing_table_includes_commercial_model_at_published_rates() -> None:
    pricing = PRICING_TABLE["gpt-4o-mini"]
    assert pricing.input_usd_per_1m_tokens == Decimal("0.150")
    assert pricing.output_usd_per_1m_tokens == Decimal("0.600")


def test_cost_for_commercial_model_computes_input_output_total() -> None:
    breakdown = cost_for(
        "gpt-4o-mini",
        input_tokens=1_000_000,
        output_tokens=500_000,
    )
    assert breakdown.input_usd == Decimal("0.150")
    assert breakdown.output_usd == Decimal("0.300")
    assert breakdown.total_usd == Decimal("0.450")


def test_cost_for_dev_model_returns_zero_breakdown() -> None:
    breakdown = cost_for(
        "qwen2.5:7b",
        input_tokens=1_234,
        output_tokens=567,
    )
    assert breakdown == CostBreakdown(
        input_usd=Decimal("0"),
        output_usd=Decimal("0"),
        total_usd=Decimal("0"),
    )


def test_cost_for_unknown_model_raises_unknown_model_error() -> None:
    with pytest.raises(UnknownModelError) as excinfo:
        cost_for("not-a-real-model", input_tokens=10, output_tokens=10)
    assert excinfo.value.model == "not-a-real-model"


def test_cost_for_accepts_custom_pricing_table() -> None:
    custom = {
        "fictional-model": ModelPricing(
            input_usd_per_1m_tokens=Decimal("1.00"),
            output_usd_per_1m_tokens=Decimal("2.00"),
        ),
    }
    breakdown = cost_for(
        "fictional-model",
        input_tokens=2_000_000,
        output_tokens=1_000_000,
        pricing_table=custom,
    )
    assert breakdown.input_usd == Decimal("2.00")
    assert breakdown.output_usd == Decimal("2.00")
    assert breakdown.total_usd == Decimal("4.00")


def test_cost_for_zero_token_call_returns_zero_breakdown_for_commercial_model() -> None:
    # Boundary: a zero-token call (e.g. an aborted request) computes
    # zero cost rather than raising. The cost helper does not gate on
    # token count — token count is the adapter's measurement, the helper
    # turns whatever counts the adapter has into USD.
    breakdown = cost_for(
        "gpt-4o-mini",
        input_tokens=0,
        output_tokens=0,
    )
    assert breakdown.total_usd == Decimal("0")


def test_model_pricing_is_frozen() -> None:
    pricing = PRICING_TABLE["gpt-4o-mini"]
    with pytest.raises(Exception):
        pricing.input_usd_per_1m_tokens = Decimal("99")
