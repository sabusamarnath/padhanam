"""ThresholdResolver port plus ConfidenceThresholds value object (D134, S47 addendum).

D134's confidence-aware composition runs a three-case discipline
keyed off two cut-off values — the high and medium thresholds. The
S47 addendum lifts threshold resolution behind a port so the cell
source contains no numeric threshold literals: at Phase 2-A the
single-pair adapter returns the configured ``(high, medium)`` pair
from ``padhanam/config/messaging.py`` regardless of the optional
``operation_class`` argument; at Phase 2-B+ the per-operation-class
adapter activates without touching the cell.

This is the same pluggable-abstraction shape that D111 operationalised
for MetricCalculator at the producer-context altitude and that D134
applied to ConfidenceCalculator. The addendum's catch is the
interface-versus-implementation methodology candidate's fifth
instance, surfaced at the prompt-draft surface.

Per D16 shared_kernel is framework-free: this is a frozen dataclass
plus a Protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ConfidenceThresholds:
    """The high and medium cut-offs for D134's three-case discipline.

    Case 1 (proceed) fires at confidence >= ``high``; Case 2
    (PendingClarification) fires in ``[medium, high)``; Case 3
    (generic clarification) fires below ``medium``. Values are
    floats in ``[0.0, 1.0]`` with ``medium <= high``.
    """

    high: float
    medium: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.medium <= self.high <= 1.0:
            raise ValueError(
                "ConfidenceThresholds must satisfy "
                "0.0 <= medium <= high <= 1.0"
            )


@runtime_checkable
class ThresholdResolver(Protocol):
    """Threshold resolution behind a Phase-2-A-to-Phase-2-B+ swap point.

    Phase 2-A adapter: returns one configured ``ConfidenceThresholds``
    regardless of ``operation_class`` (intake-canonical portfolio
    writes per D128 are the single Phase 2-A operation class).
    Phase 2-B+ adapter: per-operation-class lookup. The cell's
    consumption signature does not change at activation; the swap is
    composition-root configuration.
    """

    def resolve(
        self, operation_class: str | None = None
    ) -> ConfidenceThresholds:
        """Return the cut-offs for ``operation_class``.

        Implementations may ignore the optional argument (Phase 2-A
        single-pair adapter) or honour it (Phase 2-B+ per-operation-
        class adapter). Callers pass ``operation_class=None`` at
        Phase 2-A; the addendum's discipline is that the cell source
        carries no numeric threshold literals.
        """
        ...


__all__ = ["ConfidenceThresholds", "ThresholdResolver"]
