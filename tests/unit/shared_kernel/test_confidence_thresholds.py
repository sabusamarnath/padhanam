"""Unit tests for ConfidenceThresholds + ThresholdResolver (D134, S47 addendum)."""

from __future__ import annotations

import pytest

from contexts.messaging.adapters.threshold_single_pair import (
    SinglePairThresholdResolverAdapter,
)
from shared_kernel.confidence_thresholds import (
    ConfidenceThresholds,
    ThresholdResolver,
)


def test_confidence_thresholds_happy_path() -> None:
    thresholds = ConfidenceThresholds(high=0.8, medium=0.5)
    assert thresholds.high == 0.8
    assert thresholds.medium == 0.5


def test_confidence_thresholds_reject_medium_above_high() -> None:
    with pytest.raises(ValueError, match=r"medium <= high"):
        ConfidenceThresholds(high=0.5, medium=0.8)


def test_confidence_thresholds_reject_out_of_range() -> None:
    with pytest.raises(ValueError):
        ConfidenceThresholds(high=1.2, medium=0.5)
    with pytest.raises(ValueError):
        ConfidenceThresholds(high=0.8, medium=-0.1)


def test_confidence_thresholds_allows_equal_high_medium() -> None:
    """Edge case: a degenerate two-band cell collapses Case 2 to empty."""
    thresholds = ConfidenceThresholds(high=0.5, medium=0.5)
    assert thresholds.high == thresholds.medium


def test_single_pair_adapter_returns_configured_thresholds() -> None:
    thresholds = ConfidenceThresholds(high=0.8, medium=0.5)
    adapter = SinglePairThresholdResolverAdapter(thresholds=thresholds)
    assert adapter.resolve() is thresholds


def test_single_pair_adapter_ignores_operation_class() -> None:
    """Phase 2-A: the adapter returns the same thresholds for every class."""
    thresholds = ConfidenceThresholds(high=0.8, medium=0.5)
    adapter = SinglePairThresholdResolverAdapter(thresholds=thresholds)
    assert adapter.resolve("portfolio_write") is thresholds
    assert adapter.resolve("audit_drill_down") is thresholds
    assert adapter.resolve(None) is thresholds


def test_single_pair_adapter_is_protocol_conformant() -> None:
    """Adapter satisfies the ThresholdResolver Protocol structurally."""
    adapter = SinglePairThresholdResolverAdapter(
        thresholds=ConfidenceThresholds(high=0.8, medium=0.5),
    )
    assert isinstance(adapter, ThresholdResolver)
