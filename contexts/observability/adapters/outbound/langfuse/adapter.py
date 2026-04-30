"""No-op Langfuse trace-query adapter (D27).

Vendor isolation: this is the only directory permitted to import
``langfuse``. The import-linter contract confines the SDK here.

S7 ships a stub: get_trace returns None for every query, so the
recommendation engine work has a no-result baseline to develop
against; list_recent_traces returns an empty list. Write attempts
raise NotImplementedError because the read path is read-only by
design — the write side is the OTel span emission already in place
through LiteLLM and apps/api/.

The directory existing is what S7 needs. The real Langfuse query
implementation (HTTP GET against /api/public/traces, mapped to
TraceRecord) lands when the recommendation engine begins.
"""

from __future__ import annotations

from contexts.observability.domain.trace import TraceRecord
from shared_kernel import TenantId


class LangfuseTraceQueryAdapter:
    """No-op stub. Real implementation lands with the recommendation engine."""

    def get_trace(
        self, trace_id: str, tenant_id: TenantId
    ) -> TraceRecord | None:
        return None

    def list_recent_traces(
        self, tenant_id: TenantId, limit: int
    ) -> list[TraceRecord]:
        return []
