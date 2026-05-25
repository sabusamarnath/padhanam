"""Single-pair threshold resolver — Phase 2-A placeholder (D134, S47 addendum).

Phase 2-A implementation of the ``ThresholdResolver`` port at
``shared_kernel/confidence_thresholds.py``. Returns one configured
``ConfidenceThresholds`` regardless of the ``operation_class``
argument because Phase 2-A has a single operation class
(intake-canonical portfolio writes per D128). Phase 2-B+'s per-
operation-class adapter activates when higher-stakes operations
land; the cell's consumption signature does not change at the
trigger — the swap is composition-root configuration.

The adapter is constructed with the resolved ``(high, medium)``
pair (typically loaded from ``padhanam/config/messaging.py``'s
``MessagingSettings``). The adapter does not pull the values from
the settings module itself — the composition root extracts them
once and passes them in — so the adapter has no Pydantic Settings
dependency and the test surface stays small.

Sits at ``contexts/messaging/adapters/`` (sibling of ``outbound/``)
because the adapter has no vendor dependency, matching the
SelfReportedConfidenceAdapter convention at
``contexts/inference/adapters/`` (per the S47 base commit 3's
path-naming reconciliation).
"""

from __future__ import annotations

from shared_kernel.confidence_thresholds import (
    ConfidenceThresholds,
    ThresholdResolver,
)


class SinglePairThresholdResolverAdapter:
    """Returns the configured single pair; ignores ``operation_class``."""

    def __init__(self, *, thresholds: ConfidenceThresholds) -> None:
        self._thresholds = thresholds

    def resolve(
        self, operation_class: str | None = None
    ) -> ConfidenceThresholds:
        """Return the configured pair — ``operation_class`` is ignored."""
        del operation_class  # Phase 2-A: single operation class, no lookup.
        return self._thresholds


__all__ = ["SinglePairThresholdResolverAdapter"]
