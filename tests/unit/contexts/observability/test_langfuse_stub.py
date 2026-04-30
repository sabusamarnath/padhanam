from __future__ import annotations

from contexts.observability.adapters.outbound.langfuse import (
    LangfuseTraceQueryAdapter,
)
from shared_kernel import TenantId


def test_no_op_adapter_returns_none_for_get_trace() -> None:
    adapter = LangfuseTraceQueryAdapter()
    assert adapter.get_trace("trace-1", TenantId("tenant-a")) is None


def test_no_op_adapter_returns_empty_list_for_recent_traces() -> None:
    adapter = LangfuseTraceQueryAdapter()
    assert adapter.list_recent_traces(TenantId("tenant-a"), limit=10) == []
