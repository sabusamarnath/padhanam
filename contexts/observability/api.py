"""Public read-only query interface for the observability context (D17).

Cross-context callers (the evaluation harness at S17b commit 4; the
recommendation engine at P11) call through here. The api facade is
the single import target for cross-context consumers; D17 forbids
reaching into ``contexts.observability.{domain,application,adapters}``
directly.

S17b grows the surface with the first application-layer use case
(``query_cost_by_trace_ids``) alongside the existing
``TraceQueryPort`` re-export. The two-layer abstraction D57 commits
has each consumer define its own port and adapter that calls this
facade rather than the port directly.
"""

from __future__ import annotations

from contexts.observability.application.query_cost_by_trace_ids import (
    query_cost_by_trace_ids,
)
from contexts.observability.domain.cost import CostBreakdown
from contexts.observability.domain.trace import TraceRecord, TraceSpan
from contexts.observability.ports import TraceQueryPort

__all__ = [
    "CostBreakdown",
    "TraceQueryPort",
    "TraceRecord",
    "TraceSpan",
    "query_cost_by_trace_ids",
]
