"""Unit test for query_cost_by_trace_ids use case.

Pass-through at S17b — the test fakes the TraceQueryPort and
verifies the use case threads its inputs through unchanged. The
structural value of the use case (D17 facade pattern, D57 two-layer
abstraction) is the architectural justification; the test asserts
that the pass-through is honest and preserves the port's
absent-on-not-found semantics.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

from contexts.observability.application.query_cost_by_trace_ids import (
    query_cost_by_trace_ids,
)
from contexts.observability.domain.cost import CostBreakdown
from contexts.observability.domain.trace import TraceRecord
from shared_kernel import TenantContext


class _FakeTraceQueryPort:
    def __init__(
        self, costs: dict[str, CostBreakdown]
    ) -> None:
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
        return {tid: self._costs[tid] for tid in trace_ids if tid in self._costs}


def _ctx() -> TenantContext:
    return TenantContext(
        tenant_id="00000000-0000-4000-8000-00000000a001",
        jurisdiction="eu-west",
        cost_attribution_id="00000000-0000-4000-8000-00000000a001",
    )


def test_use_case_passes_trace_ids_and_tenant_context_through() -> None:
    port = _FakeTraceQueryPort(
        costs={
            "t1": CostBreakdown(
                total_usd=Decimal("0.10"),
                input_usd=Decimal("0.04"),
                output_usd=Decimal("0.06"),
            )
        }
    )

    result = asyncio.run(
        query_cost_by_trace_ids(
            trace_query_port=port,
            trace_ids=["t1", "t2"],
            tenant_context=_ctx(),
        )
    )

    assert port.calls == [(("t1", "t2"), _ctx().tenant_id)]
    assert "t1" in result
    assert "t2" not in result
    assert result["t1"].total_usd == Decimal("0.10")


def test_use_case_returns_empty_dict_when_port_returns_empty() -> None:
    port = _FakeTraceQueryPort(costs={})

    result = asyncio.run(
        query_cost_by_trace_ids(
            trace_query_port=port,
            trace_ids=["t1"],
            tenant_context=_ctx(),
        )
    )

    assert result == {}
