"""Public read-only query interface for the observability context (D17).

Cross-context callers (the recommendation engine at P11; the evaluation
harness at S17b) call through here. The api facade is the single
import target for cross-context consumers; D17 forbids reaching into
``contexts.observability.{domain,application,adapters}`` directly.

S17b commit 1 grows the surface with ``CostBreakdown`` (the value
object the cost-query path returns) alongside the existing
``TraceQueryPort`` re-export. Commit 3 in the same session adds the
``query_cost_by_trace_ids`` application-layer use case to this
facade; until then this module exposes the port shape and value
objects without an application-layer entry point.
"""

from __future__ import annotations

from contexts.observability.domain.cost import CostBreakdown
from contexts.observability.domain.trace import TraceRecord, TraceSpan
from contexts.observability.ports import TraceQueryPort

__all__ = [
    "CostBreakdown",
    "TraceQueryPort",
    "TraceRecord",
    "TraceSpan",
]
