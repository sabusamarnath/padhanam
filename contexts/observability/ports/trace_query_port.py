"""TraceQueryPort — read-path abstraction for trace history.

The recommendation engine queries traces via this port. Adapters
implement against whatever observability backend stores the data —
Langfuse for the dev stack, a Padhanam-owned trace store for the
Phase 2 data-plane (deferred-decisions.md → data-plane ownership).

S7 ships a no-op adapter under adapters/outbound/langfuse/. The real
adapter lands when the recommendation engine work begins.
"""

from __future__ import annotations

from typing import Protocol

from contexts.observability.domain.trace import TraceRecord
from shared_kernel import TenantId


class TraceQueryPort(Protocol):
    def get_trace(
        self, trace_id: str, tenant_id: TenantId
    ) -> TraceRecord | None:
        """Return the trace if it exists and belongs to the tenant.

        Tenant scoping is mandatory: an adapter that returns a trace
        belonging to a different tenant fails the tenant-isolation
        contract tests (D24). Returning None for not-found is
        deliberate — the engine treats missing traces and forbidden
        traces identically from its perspective.
        """
        ...

    def list_recent_traces(
        self, tenant_id: TenantId, limit: int
    ) -> list[TraceRecord]:
        """Return up to `limit` most recent traces for the tenant."""
        ...
