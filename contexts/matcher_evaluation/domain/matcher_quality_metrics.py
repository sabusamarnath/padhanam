"""MatcherQualityMetrics — the structural quality of one matcher run (D185).

Three label-free rates over the matcher's SERVES edges and units, each tied to a
decision it informs (the metric-to-decision registry, charter/current-package):

- ``single_signal_share`` — edges on the weak ``goal-name`` keyword-on-name basis
  over all edges. The size of the noise the first loop (S91) demotes; it doubles
  as that loop's target.
- ``candidate_to_confirmed_ratio`` — CANDIDATE (0.5) edges over CONFIRMED
  (0.9 / 0.95) edges. Matcher-strength health: guessing versus confirming.
- ``orphan_rate`` — units with no edge over all units. Coverage honesty and
  seeding, tied to D171.

The counts are the source of truth (persisted); the rates are derived properties,
guarded against a zero denominator (0.0 when there is nothing to divide). Counts
and rates only — never a title, sender, subject, or any content.

Pure domain (D16): stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MatcherQualityMetrics:
    """The structural metrics of one matcher run — counts plus derived rates."""

    edge_count: int
    unit_count: int
    orphan_count: int
    single_signal_count: int
    candidate_count: int
    confirmed_count: int

    def __post_init__(self) -> None:
        for name, value in (
            ("edge_count", self.edge_count),
            ("unit_count", self.unit_count),
            ("orphan_count", self.orphan_count),
            ("single_signal_count", self.single_signal_count),
            ("candidate_count", self.candidate_count),
            ("confirmed_count", self.confirmed_count),
        ):
            if value < 0:
                raise ValueError(f"{name} must be non-negative, got {value}")

    @property
    def single_signal_share(self) -> float:
        """Weak keyword-on-name edges over all edges (0.0 when no edges)."""
        if self.edge_count == 0:
            return 0.0
        return self.single_signal_count / self.edge_count

    @property
    def candidate_to_confirmed_ratio(self) -> float:
        """CANDIDATE over CONFIRMED edges (0.0 when nothing confirmed)."""
        if self.confirmed_count == 0:
            return 0.0
        return self.candidate_count / self.confirmed_count

    @property
    def orphan_rate(self) -> float:
        """Units with no edge over all units (0.0 when no units)."""
        if self.unit_count == 0:
            return 0.0
        return self.orphan_count / self.unit_count


__all__ = ["MatcherQualityMetrics"]
