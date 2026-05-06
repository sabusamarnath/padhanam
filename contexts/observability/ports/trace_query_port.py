"""TraceQueryPort — read-path abstraction for trace history.

The recommendation engine queries traces via this port, and the
evaluation harness queries trace-level cost rollups via the same port
through a separate method (D56 — interface segregation: each method
serves a coherent access pattern; neither over-generalised). Adapters
implement against whatever observability backend stores the data —
Langfuse for the dev stack, a Padhanam-owned trace store for the
Phase 2 data-plane (deferred-decisions.md → data-plane ownership).

S17b widens the historical ``TenantId`` parameter to ``TenantContext``
per D50's propagation pattern (sub-D50 application, not a fresh
D-entry). The ``TenantContext`` is the request-scoped projection the
adapter uses to verify cross-tenant isolation: a fetched trace whose
``tenant.id`` span attribute does not match
``tenant_context.tenant_id`` is treated as not found rather than
returned to the caller.
"""

from __future__ import annotations

from typing import Protocol

from contexts.observability.domain.cost import CostBreakdown
from contexts.observability.domain.trace import TraceRecord
from shared_kernel import TenantContext


class TraceQueryPort(Protocol):
    async def get_trace(
        self, trace_id: str, tenant_context: TenantContext
    ) -> TraceRecord | None:
        """Return the trace if it exists and belongs to the tenant.

        Tenant scoping is mandatory: an adapter that returns a trace
        belonging to a different tenant fails the tenant-isolation
        contract tests (D24). Returning None for not-found is
        deliberate — the engine treats missing traces and forbidden
        traces identically from its perspective.
        """
        ...

    async def list_recent_traces(
        self, tenant_context: TenantContext, limit: int
    ) -> list[TraceRecord]:
        """Return up to ``limit`` most recent traces for the tenant."""
        ...

    async def get_costs_by_trace_ids(
        self,
        trace_ids: list[str],
        tenant_context: TenantContext,
    ) -> dict[str, CostBreakdown]:
        """Return per-trace cost breakdowns for the given trace ids.

        Trace ids that do not exist, do not carry cost data, or belong
        to a different tenant are absent from the returned dict —
        the caller distinguishes "trace not found" from
        "successfully fetched, no cost data" by structural absence,
        not by sentinel values. Cross-tenant isolation is enforced
        per-trace inside the adapter; trace-id reuse across tenants
        cannot leak cost data.

        D56 commits this method-shape: a batch cost-only access
        pattern with type-safe inputs and outputs. Widening
        ``get_trace`` to a batch form would force cost-shaped
        consumers to filter span data they do not need, so the port
        grows by adding methods rather than by widening existing
        ones.
        """
        ...
