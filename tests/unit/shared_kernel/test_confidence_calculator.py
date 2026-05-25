"""Unit tests for the ConfidenceCalculator port and self-reported adapter (D134, S47)."""

from __future__ import annotations

import pytest

from contexts.inference.adapters.confidence_self_reported import (
    SelfReportedConfidenceAdapter,
)
from shared_kernel.confidence_calculator import ConfidenceCalculator
from shared_kernel.structured_output import (
    StructuredOutputRequest,
    StructuredOutputResponse,
)


def _request() -> StructuredOutputRequest:
    return StructuredOutputRequest(
        prompt="classify this",
        schema={
            "type": "object",
            "properties": {"intent": {"type": "string"}},
            "required": ["intent"],
        },
    )


def _response(confidence: float | None) -> StructuredOutputResponse:
    return StructuredOutputResponse(
        value={"intent": "create_case"},
        confidence=confidence,
        provider_metadata={},
    )


def test_self_reported_adapter_returns_response_confidence() -> None:
    adapter = SelfReportedConfidenceAdapter()
    value = adapter.compute(request=_request(), response=_response(0.87))
    assert value == 0.87


def test_self_reported_adapter_falls_back_to_default_when_absent() -> None:
    adapter = SelfReportedConfidenceAdapter(default_when_absent=0.5)
    value = adapter.compute(request=_request(), response=_response(None))
    assert value == 0.5


def test_self_reported_adapter_default_is_configurable() -> None:
    """Operator can tune missing-signal behaviour without code change."""
    adapter = SelfReportedConfidenceAdapter(default_when_absent=0.3)
    value = adapter.compute(request=_request(), response=_response(None))
    assert value == 0.3


def test_self_reported_adapter_clamps_above_one() -> None:
    adapter = SelfReportedConfidenceAdapter()
    value = adapter.compute(request=_request(), response=_response(1.5))
    assert value == 1.0


def test_self_reported_adapter_clamps_below_zero() -> None:
    adapter = SelfReportedConfidenceAdapter()
    value = adapter.compute(request=_request(), response=_response(-0.2))
    assert value == 0.0


def test_self_reported_adapter_rejects_out_of_range_default() -> None:
    with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
        SelfReportedConfidenceAdapter(default_when_absent=1.5)


def test_self_reported_adapter_is_protocol_conformant() -> None:
    """Adapter satisfies the ConfidenceCalculator Protocol structurally."""
    adapter = SelfReportedConfidenceAdapter()
    assert isinstance(adapter, ConfidenceCalculator)
