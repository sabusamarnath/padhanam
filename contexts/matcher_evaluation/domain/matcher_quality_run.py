"""MatcherQualityRun — the matcher-quality run aggregate (D185).

The producer's record of one matcher measurement: the metrics computed on one
``correlate_goal_facets`` run, stamped with the tenant and the time. The reader
port returns these; S91's RecommendationRule reads the latest (and re-measures
the "after" against the S90 baseline).

Right-sized against ``retrieval_evaluation``'s ``EvaluationRun``: that aggregate
carries a running → completed/failed status lifecycle because it orchestrates a
long multi-strategy run; the matcher measurement is a single synchronous, atomic
computation at the correlate hook, so there is no in-flight state — a run is
always a completed measurement. (When the producer later grows an asynchronous
or partial path, the status lifecycle lands then, the second-instance discipline.)

Pure domain (D16): stdlib dataclasses only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from contexts.matcher_evaluation.domain.matcher_quality_metrics import (
    MatcherQualityMetrics,
)


@dataclass(frozen=True)
class MatcherQualityRun:
    """One matcher-quality measurement, stamped with tenant and time."""

    id: UUID
    tenant_id: UUID
    jurisdiction: str
    computed_at: datetime
    metrics: MatcherQualityMetrics

    def __post_init__(self) -> None:
        if not self.jurisdiction.strip():
            raise ValueError("jurisdiction must be non-empty")


__all__ = ["MatcherQualityRun"]
