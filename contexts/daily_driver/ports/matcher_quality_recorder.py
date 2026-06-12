"""Recorder port for matcher-quality observability (D185, S90).

The matcher's observe-only seam: ``correlate_goal_facets`` calls a recorder with
the final SERVES edges and the units, right before it replaces the edges. The
recorder reads them and records a quality measurement; it never mutates the edge
set, so the matcher's output is unchanged whether or not a recorder is wired.

The port is **daily_driver's own**, typed in daily_driver's domain (``GoalEdge``,
``UnitView``) — so this context imports nothing from the producer
(``matcher_evaluation``). The bridge that projects these edges to the producer's
neutral sample lives at the composition root (``apps/``), where the independence
contracts (D17) permit the cross-context join. Default-None at the call site, so
correlation runs unchanged when observability is not wired.

Ports layer is pure per D16.
"""

from __future__ import annotations

from typing import Protocol

from contexts.daily_driver.domain.goal_assessment import GoalEdge
from contexts.daily_driver.domain.unit_view import UnitView
from shared_kernel import ActorContext


class MatcherQualityRecorder(Protocol):
    """Records a quality measurement of one matcher run (observe-only)."""

    async def record(
        self,
        *,
        actor: ActorContext,
        edges: tuple[GoalEdge, ...],
        units: tuple[UnitView, ...],
    ) -> None:
        """Measure + persist the run's quality. Must not mutate ``edges``."""
        ...


__all__ = ["MatcherQualityRecorder"]
