"""CostQueryAdapter — evaluation-side bridge to observability (D57).

The cross-context boundary lives here. The adapter implements
evaluation's CostQueryPort by calling
``contexts.observability.api.query_cost_by_trace_ids``, the legal
import target per D17's facade pattern. Evaluation's use cases are
free of vendor knowledge (D27 holds end-to-end: vendor-specific
Langfuse code lives only in
``contexts/observability/adapters/outbound/langfuse/``); evaluation's
adapter knows only that observability exposes the use case.

Construction takes the observability ``TraceQueryPort`` so the
production wiring at apps/api/main.py composes the
LangfuseHTTPTraceQueryAdapter once and threads it through both
observability's own consumers and evaluation's CostQueryPort. Tests
inject a fake TraceQueryPort.
"""

from __future__ import annotations

from contexts.observability.api import (
    CostBreakdown,
    TraceQueryPort,
    query_cost_by_trace_ids,
)
from shared_kernel import TenantContext


class CostQueryAdapter:
    """Adapter for evaluation's CostQueryPort calling observability's
    ``query_cost_by_trace_ids`` use case (D57 two-layer abstraction).
    """

    def __init__(self, trace_query_port: TraceQueryPort) -> None:
        self._trace_query_port = trace_query_port

    async def get_costs_by_trace_ids(
        self,
        trace_ids: list[str],
        tenant_context: TenantContext,
    ) -> dict[str, CostBreakdown]:
        return await query_cost_by_trace_ids(
            trace_query_port=self._trace_query_port,
            trace_ids=trace_ids,
            tenant_context=tenant_context,
        )
