from __future__ import annotations

import asyncio

from contexts.observability.adapters.outbound.langfuse import (
    LangfuseTraceQueryAdapter,
)
from shared_kernel import TenantContext


_TENANT = TenantContext(
    tenant_id="00000000-0000-4000-8000-00000000a001",
    jurisdiction="eu-west",
    cost_attribution_id="00000000-0000-4000-8000-00000000a001",
)


def test_no_op_adapter_returns_none_for_get_trace() -> None:
    adapter = LangfuseTraceQueryAdapter()
    assert asyncio.run(adapter.get_trace("trace-1", _TENANT)) is None


def test_no_op_adapter_returns_empty_list_for_recent_traces() -> None:
    adapter = LangfuseTraceQueryAdapter()
    assert asyncio.run(adapter.list_recent_traces(_TENANT, limit=10)) == []


def test_no_op_adapter_returns_empty_dict_for_costs_by_trace_ids() -> None:
    adapter = LangfuseTraceQueryAdapter()
    assert (
        asyncio.run(
            adapter.get_costs_by_trace_ids(
                ["trace-1", "trace-2"], _TENANT
            )
        )
        == {}
    )
