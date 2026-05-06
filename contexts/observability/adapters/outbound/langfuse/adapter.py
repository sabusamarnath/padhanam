"""No-op Langfuse trace-query adapter (D27).

Vendor isolation: this is the only directory permitted to import
``langfuse`` per import-linter, and the only directory that imports
``httpx`` for the Langfuse public API. The S7 no-op stub kept the
import-linter and cross-context wiring shape real before any consumer
existed; S17b replaces the stub with the real HTTP-against-public-API
implementation in ``http_adapter.py``. This module is retained as the
no-op fallback used by unit tests that exercise the port-shape
contract without standing up a Langfuse instance.

Real implementation lands at S17b alongside cost-per-successful-task,
the first cross-context consumer of the port.
"""

from __future__ import annotations

from contexts.observability.domain.cost import CostBreakdown
from contexts.observability.domain.trace import TraceRecord
from shared_kernel import TenantContext


class LangfuseTraceQueryAdapter:
    """No-op stub. Real adapter lives in
    ``contexts/observability/adapters/outbound/langfuse/http_adapter.py``."""

    async def get_trace(
        self, trace_id: str, tenant_context: TenantContext
    ) -> TraceRecord | None:
        return None

    async def list_recent_traces(
        self, tenant_context: TenantContext, limit: int
    ) -> list[TraceRecord]:
        return []

    async def get_costs_by_trace_ids(
        self,
        trace_ids: list[str],
        tenant_context: TenantContext,
    ) -> dict[str, CostBreakdown]:
        return {}
