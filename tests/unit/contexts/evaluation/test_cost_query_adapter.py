"""Unit test for evaluation's CostQueryAdapter.

The adapter is the cross-context bridge per D57. The test fakes the
observability TraceQueryPort and verifies the adapter threads inputs
through ``contexts.observability.api.query_cost_by_trace_ids``
unchanged.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

from contexts.evaluation.adapters.outbound.cost_query_adapter import (
    CostQueryAdapter,
)
from contexts.observability.domain.cost import CostBreakdown
from contexts.observability.domain.trace import TraceRecord
from shared_kernel import TenantContext


class _FakeTraceQueryPort:
    def __init__(self, costs: dict[str, CostBreakdown]) -> None:
        self._costs = costs
        self.calls: list[tuple[tuple[str, ...], str]] = []

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
        self.calls.append((tuple(trace_ids), tenant_context.tenant_id))
        return {
            tid: self._costs[tid] for tid in trace_ids if tid in self._costs
        }


def _ctx() -> TenantContext:
    return TenantContext(
        tenant_id="00000000-0000-4000-8000-00000000a001",
        jurisdiction="eu-west",
        cost_attribution_id="00000000-0000-4000-8000-00000000a001",
    )


def test_adapter_forwards_to_observability_use_case() -> None:
    port = _FakeTraceQueryPort(
        costs={
            "t1": CostBreakdown(
                total_usd=Decimal("0.42"),
                input_usd=Decimal("0.20"),
                output_usd=Decimal("0.22"),
            )
        }
    )
    adapter = CostQueryAdapter(trace_query_port=port)

    result = asyncio.run(
        adapter.get_costs_by_trace_ids(
            ["t1", "missing"], tenant_context=_ctx()
        )
    )

    assert port.calls == [(("t1", "missing"), _ctx().tenant_id)]
    assert "t1" in result
    assert "missing" not in result
    assert result["t1"].total_usd == Decimal("0.42")


def test_adapter_returns_empty_dict_for_empty_input() -> None:
    port = _FakeTraceQueryPort(costs={})
    adapter = CostQueryAdapter(trace_query_port=port)

    result = asyncio.run(
        adapter.get_costs_by_trace_ids([], tenant_context=_ctx())
    )

    assert result == {}
