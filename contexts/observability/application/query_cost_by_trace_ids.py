"""query_cost_by_trace_ids use case (D17, D57).

The first use case in observability's application layer. Cross-context
callers (the evaluation harness's CostQueryAdapter at S17b; the
recommendation engine's aggregation queries at P11) consume this
through the api facade per D17 — never reaching into the port or
adapter directly.

The use case is a pass-through to ``TraceQueryPort.get_costs_by_trace_ids``
at S17b. The application-layer surface exists for two reasons that
both come from D17 and D57:

1. D17 mandates that cross-context calls go through application-layer
   use cases via the api facade. The application layer is the legal
   surface; ports are the internal abstraction. Even when the use
   case body is one line, the structural placement is load-bearing.

2. D57 commits the two-layer cost-query abstraction. Future hooks
   (caching, partial-failure telemetry, cross-trace aggregation)
   land here without touching the port or the adapter, and without
   requiring every consumer (evaluation today, recommendation engine
   tomorrow) to re-implement them. The pass-through shape at S17b
   is intentional — adding hooks ahead of consumers would be paper
   architecture.
"""

from __future__ import annotations

from contexts.observability.domain.cost import CostBreakdown
from contexts.observability.ports import TraceQueryPort
from shared_kernel import TenantContext


async def query_cost_by_trace_ids(
    *,
    trace_query_port: TraceQueryPort,
    trace_ids: list[str],
    tenant_context: TenantContext,
) -> dict[str, CostBreakdown]:
    """Return per-trace cost breakdowns for the given trace ids.

    Trace ids that do not exist, do not carry cost data, or belong to
    a different tenant are absent from the returned dict — the same
    structural-absence contract the port commits.
    """
    return await trace_query_port.get_costs_by_trace_ids(
        trace_ids, tenant_context
    )
