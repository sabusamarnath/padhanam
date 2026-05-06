"""CostQueryPort — evaluation's read-side abstraction over trace costs.

The cost-per-successful-task use case at S17b reads cost data via
this port; the production wiring at apps/api/main.py constructs the
adapter that bridges to ``contexts.observability.api.query_cost_by_trace_ids``
per D57's two-layer abstraction. Each context owns its own cost-query
abstraction; cross-context coupling lives only at the adapter, never
at the use case.

CostBreakdown is imported from ``contexts.observability.api`` rather
than re-defined in evaluation's domain. The value object is referentially
shared across contexts via the api facade, the same way Tenant
context types are shared via shared_kernel — except cost data is
observability's authority, not shared_kernel's.
"""

from __future__ import annotations

from typing import Protocol

from contexts.observability.api import CostBreakdown
from shared_kernel import TenantContext


class CostQueryPort(Protocol):
    async def get_costs_by_trace_ids(
        self,
        trace_ids: list[str],
        tenant_context: TenantContext,
    ) -> dict[str, CostBreakdown]:
        """Return per-trace cost breakdowns for the given trace ids.

        Trace ids that do not exist, do not carry cost data, or
        belong to a different tenant are absent from the returned
        dict. Adapters enforce cross-tenant isolation and the
        absence-on-not-found contract; this port does not allow
        adapters to leak cross-tenant data through any return path.
        """
        ...
