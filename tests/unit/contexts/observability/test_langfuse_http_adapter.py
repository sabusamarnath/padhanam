"""Unit tests for LangfuseHTTPTraceQueryAdapter.

Use httpx.MockTransport so the adapter exercises its real HTTP path
without standing up a Langfuse instance. Each test constructs a
mock-trace payload mirroring the live Langfuse public-API response
shape captured at S17b pre-write reconciliation:

  - trace top-level: id, metadata{attributes, ...}, observations[]
  - each observation: metadata{attributes{gen_ai.*, tenant.*, ...}}

Cost values are returned as strings by Langfuse's OTLP→ClickHouse
pipeline (OTel float attributes are serialised as strings on the
read path); the adapter parses to Decimal.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

import httpx
import pytest

from contexts.observability.adapters.outbound.langfuse.http_adapter import (
    LangfuseHTTPTraceQueryAdapter,
)
from padhanam.config import ObservabilitySettings
from shared_kernel import TenantContext


_TENANT_A = TenantContext(
    tenant_id="00000000-0000-4000-8000-00000000a001",
    jurisdiction="eu-west",
    cost_attribution_id="00000000-0000-4000-8000-00000000a001",
)


def _settings() -> ObservabilitySettings:
    return ObservabilitySettings(
        langfuse_public_key="pk-lf-dev",
        langfuse_secret_key="sk-lf-dev",
        langfuse_api_base_url="http://langfuse-web:3000",
    )


def _trace_payload(
    *,
    trace_id: str,
    tenant_id: str | None = "00000000-0000-4000-8000-00000000a001",
    cost_input: str = "0.012",
    cost_output: str = "0.024",
    cost_total: str = "0.036",
    observation_count: int = 1,
) -> dict[str, Any]:
    """Build a Langfuse trace payload mirroring the live shape."""
    attrs: dict[str, Any] = {
        "gen_ai.system": "litellm",
        "gen_ai.request.model": "qwen2.5:7b",
    }
    if tenant_id is not None:
        attrs["tenant.id"] = tenant_id
        attrs["tenant.jurisdiction"] = "eu-west"
        attrs["tenant.cost_attribution_id"] = tenant_id
    if cost_total is not None:
        attrs["gen_ai.cost.input_usd"] = cost_input
        attrs["gen_ai.cost.output_usd"] = cost_output
        attrs["gen_ai.cost.total_usd"] = cost_total
        attrs["gen_ai.cost.pricing_status"] = "table_hit"
    observations = [
        {
            "id": f"obs-{i}",
            "traceId": trace_id,
            "parentObservationId": None,
            "type": "GENERATION",
            "name": "chat qwen2.5:7b",
            "startTime": "2026-05-06T19:07:11.442Z",
            "endTime": "2026-05-06T19:07:13.298Z",
            "metadata": {"attributes": dict(attrs)},
        }
        for i in range(observation_count)
    ]
    return {
        "id": trace_id,
        "name": "chat qwen2.5:7b",
        "metadata": {"attributes": dict(attrs)},
        "observations": observations,
    }


def _build_adapter(
    handler,
    *,
    concurrency: int = 10,
) -> LangfuseHTTPTraceQueryAdapter:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(
        base_url="http://langfuse-web:3000",
        transport=transport,
        timeout=httpx.Timeout(5.0),
    )
    return LangfuseHTTPTraceQueryAdapter(
        settings=_settings(),
        client=client,
        concurrency=concurrency,
    )


# ---------------------------------------------------------------------
# get_trace
# ---------------------------------------------------------------------


def test_get_trace_returns_record_on_200() -> None:
    payload = _trace_payload(trace_id="trace-1")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/public/traces/trace-1"
        return httpx.Response(200, json=payload)

    adapter = _build_adapter(handler)
    record = asyncio.run(adapter.get_trace("trace-1", _TENANT_A))
    assert record is not None
    assert record.trace_id == "trace-1"
    assert record.tenant_id == _TENANT_A.tenant_id
    assert len(record.spans) == 1
    assert record.spans[0].name == "chat qwen2.5:7b"


def test_get_trace_returns_none_on_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    adapter = _build_adapter(handler)
    assert asyncio.run(adapter.get_trace("missing", _TENANT_A)) is None


def test_get_trace_returns_none_on_401_auth_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    adapter = _build_adapter(handler)
    assert asyncio.run(adapter.get_trace("any", _TENANT_A)) is None


def test_get_trace_filters_cross_tenant() -> None:
    """Tenant-mismatch on the fetched trace's tenant.id is treated as
    not-found. Cross-tenant isolation at the adapter layer is the
    architectural protection against trace-id reuse leakage in a
    shared Langfuse instance.
    """
    other_tenant_payload = _trace_payload(
        trace_id="t1",
        tenant_id="00000000-0000-4000-8000-00000000b002",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=other_tenant_payload)

    adapter = _build_adapter(handler)
    assert asyncio.run(adapter.get_trace("t1", _TENANT_A)) is None


def test_get_trace_rejects_trace_without_tenant_id() -> None:
    """Traces with no tenant.id at all are rejected — the
    LiteLLMAdapter emits the attribute on every completion span per
    D50, so absence is wiring drift, not legitimate traffic.
    """
    payload = _trace_payload(trace_id="t1", tenant_id=None)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    adapter = _build_adapter(handler)
    assert asyncio.run(adapter.get_trace("t1", _TENANT_A)) is None


# ---------------------------------------------------------------------
# get_costs_by_trace_ids
# ---------------------------------------------------------------------


def test_get_costs_by_trace_ids_returns_decimal_breakdowns() -> None:
    payload = _trace_payload(
        trace_id="t1",
        cost_input="0.10",
        cost_output="0.20",
        cost_total="0.30",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    adapter = _build_adapter(handler)
    costs = asyncio.run(
        adapter.get_costs_by_trace_ids(["t1"], _TENANT_A)
    )
    assert "t1" in costs
    assert costs["t1"].total_usd == Decimal("0.30")
    assert costs["t1"].input_usd == Decimal("0.10")
    assert costs["t1"].output_usd == Decimal("0.20")


def test_get_costs_by_trace_ids_aggregates_across_observations() -> None:
    """A trace with two cost-bearing observations sums into the
    returned CostBreakdown. The bare-script case (one obs) and the
    FastAPI-rooted case (chat as one of multiple observations) both
    flow through the same aggregation path.
    """
    payload = _trace_payload(
        trace_id="t1",
        cost_input="0.05",
        cost_output="0.10",
        cost_total="0.15",
        observation_count=2,
    )
    # Trace-level metadata also carries cost attrs in this fixture;
    # the adapter's aggregation deliberately sums observations only
    # to avoid double-counting the trace-root carrier.

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    adapter = _build_adapter(handler)
    costs = asyncio.run(
        adapter.get_costs_by_trace_ids(["t1"], _TENANT_A)
    )
    assert costs["t1"].total_usd == Decimal("0.30")
    assert costs["t1"].input_usd == Decimal("0.10")
    assert costs["t1"].output_usd == Decimal("0.20")


def test_get_costs_by_trace_ids_partial_success() -> None:
    """Missing traces, cross-tenant traces, and traces without cost
    attributes are absent from the returned dict — the caller
    distinguishes by structural absence, not sentinel values.
    """
    payloads: dict[str, dict[str, Any]] = {
        "t1": _trace_payload(
            trace_id="t1", cost_total="0.10", cost_input="0.04", cost_output="0.06"
        ),
        # cross-tenant: present but for a different tenant
        "t3": _trace_payload(
            trace_id="t3",
            tenant_id="00000000-0000-4000-8000-00000000b002",
        ),
        # no-cost: legitimate but no gen_ai.cost.* attributes
        "t4": {
            "id": "t4",
            "metadata": {
                "attributes": {"tenant.id": _TENANT_A.tenant_id}
            },
            "observations": [
                {
                    "id": "obs-x",
                    "type": "EVENT",
                    "metadata": {
                        "attributes": {"tenant.id": _TENANT_A.tenant_id}
                    },
                }
            ],
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        trace_id = request.url.path.rsplit("/", 1)[-1]
        if trace_id == "t2":
            return httpx.Response(404, json={"error": "not found"})
        return httpx.Response(200, json=payloads[trace_id])

    adapter = _build_adapter(handler)
    costs = asyncio.run(
        adapter.get_costs_by_trace_ids(
            ["t1", "t2", "t3", "t4"], _TENANT_A
        )
    )
    assert set(costs.keys()) == {"t1"}
    assert costs["t1"].total_usd == Decimal("0.10")


def test_get_costs_by_trace_ids_handles_empty_input() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail(  # noqa: PT017 - test-helper fail signals adapter bug
            "adapter must not call HTTP when trace_ids is empty"
        )

    adapter = _build_adapter(handler)
    assert asyncio.run(adapter.get_costs_by_trace_ids([], _TENANT_A)) == {}


# ---------------------------------------------------------------------
# wait_for_trace_availability (D59, S18)
# ---------------------------------------------------------------------


def test_wait_for_trace_availability_returns_true_on_immediate_hit() -> None:
    """Trace is already ingested — first poll succeeds, no sleeping
    needed and no further HTTP calls."""
    payload = _trace_payload(trace_id="trace-1")
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=payload)

    adapter = _build_adapter(handler)
    result = asyncio.run(
        adapter.wait_for_trace_availability(
            "trace-1",
            _TENANT_A,
            timeout_seconds=5.0,
            poll_interval_seconds=0.001,
        )
    )
    assert result is True
    assert calls == 1


def test_wait_for_trace_availability_returns_true_after_polling() -> None:
    """Trace is not yet ingested at first; appears after a few polls.
    Helper retries until the trace materialises."""
    payload = _trace_payload(trace_id="trace-1")
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(404, json={"error": "not found"})
        return httpx.Response(200, json=payload)

    adapter = _build_adapter(handler)
    result = asyncio.run(
        adapter.wait_for_trace_availability(
            "trace-1",
            _TENANT_A,
            timeout_seconds=5.0,
            poll_interval_seconds=0.001,
        )
    )
    assert result is True
    assert calls == 3


def test_wait_for_trace_availability_returns_false_on_timeout() -> None:
    """Trace never appears within the timeout window. Helper returns
    False rather than blocking forever or raising."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404, json={"error": "not found"})

    adapter = _build_adapter(handler)
    result = asyncio.run(
        adapter.wait_for_trace_availability(
            "trace-1",
            _TENANT_A,
            timeout_seconds=0.05,
            poll_interval_seconds=0.01,
        )
    )
    assert result is False
    assert calls >= 1


def test_wait_for_trace_availability_treats_cross_tenant_trace_as_unavailable() -> None:
    """A trace owned by a different tenant looks identical to a
    not-yet-ingested trace from this tenant's perspective. The helper
    times out rather than reporting the trace as available."""
    other_tenant_payload = _trace_payload(
        trace_id="trace-1",
        tenant_id="00000000-0000-4000-8000-00000000b002",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=other_tenant_payload)

    adapter = _build_adapter(handler)
    result = asyncio.run(
        adapter.wait_for_trace_availability(
            "trace-1",
            _TENANT_A,
            timeout_seconds=0.05,
            poll_interval_seconds=0.01,
        )
    )
    assert result is False
