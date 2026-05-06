"""LangfuseHTTPTraceQueryAdapter — real Langfuse public API implementation.

Vendor isolation per D27: this is the only file in the codebase that
constructs HTTP requests against Langfuse's public API. Domain code
sees only TraceRecord, TraceSpan, and CostBreakdown; the adapter owns
the wire-shape→domain-shape translation.

Authentication is HTTP Basic with ``langfuse_public_key`` and
``langfuse_secret_key`` from ``ObservabilitySettings`` (the same
credentials Langfuse OTLP ingestion already consumes per D49). The
in-network base URL resolves to ``http://langfuse-web:3000`` in the
local Compose stack; production deployments override via the
``LANGFUSE_API_BASE_URL`` env binding on
``ObservabilitySettings``.

Cross-tenant isolation at the adapter layer is load-bearing for the
case study's tenant-isolation discipline (D24): every fetched trace's
``tenant.id`` span attribute is verified against
``tenant_context.tenant_id`` before any data leaves the adapter. A
trace whose tenant.id does not match — whether through ingestion bug,
shared trace-id reuse across tenants, or active cross-tenant probe —
is treated as not-found. The discipline holds even if the upstream
ingestion path emits a malformed span; the adapter does not trust the
backend to enforce isolation.

Batch fetch posture: Langfuse exposes no list-by-ids endpoint; the
adapter fans out N parallel singular fetches via ``asyncio.gather``
under a concurrency-limit semaphore (default 10) so the cost-query
path scales without saturating the Langfuse worker. If/when the
public API surfaces a batch endpoint, the swap is local to this
adapter.

Cost-attribute parsing: D49 emits ``gen_ai.cost.{input,output,total}_usd``
as float span attributes; Langfuse's OTLP→ClickHouse pipeline stores
attributes as strings, so the adapter parses to ``Decimal`` (not
``float``) on read. Costs are aggregated across every observation on
a trace that carries the attributes — for FastAPI-rooted traces the
chat child carries cost data; for bare-script-rooted traces (the
S17b e2e test) the chat span itself is root and carries cost data.
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from contexts.observability.domain.cost import CostBreakdown
from contexts.observability.domain.trace import TraceRecord, TraceSpan
from padhanam.config import ObservabilitySettings
from shared_kernel import TenantContext


logger = logging.getLogger(__name__)


_TRACE_ENDPOINT = "/api/public/traces/{trace_id}"

# Tenant attribute the LiteLLMAdapter emits per D50; must match across
# adapter and observability span attribute namespace.
_TENANT_ID_ATTR = "tenant.id"

# D49 cost-attribute names.
_COST_TOTAL = "gen_ai.cost.total_usd"
_COST_INPUT = "gen_ai.cost.input_usd"
_COST_OUTPUT = "gen_ai.cost.output_usd"

# Concurrency cap for parallel singular fetches under
# get_costs_by_trace_ids. Sized to keep Langfuse worker pressure
# bounded while still amortising over batch-shaped consumers.
_DEFAULT_CONCURRENCY = 10


class LangfuseHTTPTraceQueryAdapter:
    """TraceQueryPort implementation against Langfuse's public API."""

    def __init__(
        self,
        settings: ObservabilitySettings | None = None,
        client: httpx.AsyncClient | None = None,
        concurrency: int = _DEFAULT_CONCURRENCY,
    ) -> None:
        self._settings = settings or ObservabilitySettings()
        self._client = client
        self._owns_client = client is None
        self._concurrency = concurrency

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.langfuse_api_base_url,
                auth=(
                    self._settings.langfuse_public_key,
                    self._settings.langfuse_secret_key,
                ),
                timeout=httpx.Timeout(10.0),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def get_trace(
        self, trace_id: str, tenant_context: TenantContext
    ) -> TraceRecord | None:
        payload = await self._fetch_trace(trace_id)
        if payload is None:
            return None
        if not _trace_matches_tenant(payload, tenant_context):
            return None
        return _payload_to_record(payload)

    async def list_recent_traces(
        self, tenant_context: TenantContext, limit: int
    ) -> list[TraceRecord]:
        # Not a Phase 1 consumer; the recommendation engine will land
        # this with its own filter shape (per-tenant, per-time-window)
        # at P11. Returning empty here rather than half-implementing a
        # filter that has no reader yet.
        return []

    async def get_costs_by_trace_ids(
        self,
        trace_ids: list[str],
        tenant_context: TenantContext,
    ) -> dict[str, CostBreakdown]:
        if not trace_ids:
            return {}
        semaphore = asyncio.Semaphore(self._concurrency)

        async def _one(tid: str) -> tuple[str, CostBreakdown | None]:
            async with semaphore:
                payload = await self._fetch_trace(tid)
            if payload is None:
                return tid, None
            if not _trace_matches_tenant(payload, tenant_context):
                return tid, None
            return tid, _payload_to_cost(payload)

        results = await asyncio.gather(
            *(_one(tid) for tid in trace_ids)
        )
        return {tid: cost for tid, cost in results if cost is not None}

    async def _fetch_trace(self, trace_id: str) -> dict[str, Any] | None:
        client = await self._get_client()
        try:
            response = await client.get(
                _TRACE_ENDPOINT.format(trace_id=trace_id)
            )
        except httpx.HTTPError as e:
            logger.warning("langfuse trace fetch failed: %s", e)
            return None
        if response.status_code == 404:
            return None
        if response.status_code == 401:
            logger.warning(
                "langfuse trace fetch unauthorized (401); check credentials"
            )
            return None
        if response.status_code >= 400:
            logger.warning(
                "langfuse trace fetch returned %s for trace_id=%s",
                response.status_code,
                trace_id,
            )
            return None
        try:
            return response.json()
        except ValueError:
            logger.warning(
                "langfuse trace fetch returned non-JSON for trace_id=%s",
                trace_id,
            )
            return None


# ---------------------------------------------------------------------
# Wire-shape → domain mapping
# ---------------------------------------------------------------------


def _trace_matches_tenant(
    payload: dict[str, Any], tenant_context: TenantContext
) -> bool:
    """Verify ``tenant.id`` on the trace matches the requesting context.

    Cross-tenant isolation is enforced positively: a trace passes the
    check only when at least one carrier (trace-level metadata or any
    observation's metadata) declares ``tenant.id`` and the value
    matches. Traces with no ``tenant.id`` at all are rejected — the
    LiteLLMAdapter emits the attribute on every completion span per
    D50, so absence is wiring drift, not legitimate traffic.
    """
    expected = tenant_context.tenant_id
    saw_tenant_id = False
    for attrs in _iter_attribute_dicts(payload):
        actual = attrs.get(_TENANT_ID_ATTR)
        if actual is None:
            continue
        saw_tenant_id = True
        if str(actual) != expected:
            return False
    return saw_tenant_id


def _payload_to_cost(payload: dict[str, Any]) -> CostBreakdown | None:
    """Aggregate ``gen_ai.cost.*`` attributes across all observations.

    Returns None when no observation on the trace carries cost data
    (e.g. non-LLM traces, or LLM traces emitted before the D49
    cost-capture wiring landed). Aggregation is a sum across
    observations: a trace with two completion spans returns the
    combined cost.
    """
    total = Decimal("0")
    input_ = Decimal("0")
    output = Decimal("0")
    saw_cost = False
    # Trace-level attributes (root span) when the root is the chat
    # span itself; observation-level when the root is e.g. a FastAPI
    # request and chat is a child. Iterating both is the structurally
    # honest approach because observation-as-root vs observation-as-
    # child depends on the call path, not the wire shape.
    for attrs in _iter_attribute_dicts(payload, include_trace_root=False):
        if _COST_TOTAL not in attrs:
            continue
        saw_cost = True
        total += _to_decimal(attrs.get(_COST_TOTAL))
        input_ += _to_decimal(attrs.get(_COST_INPUT))
        output += _to_decimal(attrs.get(_COST_OUTPUT))
    if not saw_cost:
        # Fall back to trace-level attributes when no observation
        # carries cost (the bare-script case where the chat span is
        # the trace root and the observation array is just that one
        # span — but the root may have already been counted; this
        # branch covers the zero-observation case where the trace's
        # only carrier is the trace-level metadata).
        root_attrs = _trace_metadata_attributes(payload)
        if _COST_TOTAL in root_attrs:
            saw_cost = True
            total = _to_decimal(root_attrs.get(_COST_TOTAL))
            input_ = _to_decimal(root_attrs.get(_COST_INPUT))
            output = _to_decimal(root_attrs.get(_COST_OUTPUT))
    if not saw_cost:
        return None
    return CostBreakdown(
        total_usd=total, input_usd=input_, output_usd=output
    )


def _payload_to_record(payload: dict[str, Any]) -> TraceRecord:
    """Map a Langfuse trace payload to the domain TraceRecord.

    Spans are unordered in the domain; the engine traverses by
    parent_span_id (per ``trace.py`` docstring). Only fields the
    domain shape exposes are translated; Langfuse-specific fields
    (htmlPath, bookmarked, projectId) stay in adapter scope.
    """
    spans: list[TraceSpan] = []
    for obs in payload.get("observations") or []:
        if not isinstance(obs, dict):
            continue
        attrs = _observation_attributes(obs)
        spans.append(
            TraceSpan(
                span_id=str(obs.get("id", "")),
                parent_span_id=(
                    str(obs.get("parentObservationId"))
                    if obs.get("parentObservationId") is not None
                    else None
                ),
                name=str(obs.get("name", "")),
                start_time_ns=_iso_to_ns(obs.get("startTime")),
                end_time_ns=_iso_to_ns(obs.get("endTime")),
                attributes=dict(attrs),
            )
        )
    tenant_id = ""
    for attrs in _iter_attribute_dicts(payload):
        candidate = attrs.get(_TENANT_ID_ATTR)
        if candidate is not None:
            tenant_id = str(candidate)
            break
    return TraceRecord(
        trace_id=str(payload.get("id", "")),
        tenant_id=tenant_id,
        spans=spans,
    )


def _iter_attribute_dicts(
    payload: dict[str, Any], include_trace_root: bool = True
):
    """Yield every ``metadata.attributes`` dict on the trace.

    Order: trace-level attributes first (when ``include_trace_root``),
    then each observation's attributes. Callers that want only
    observation-level attributes pass ``include_trace_root=False``.
    """
    if include_trace_root:
        yield _trace_metadata_attributes(payload)
    for obs in payload.get("observations") or []:
        if isinstance(obs, dict):
            yield _observation_attributes(obs)


def _trace_metadata_attributes(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return {}
    attrs = metadata.get("attributes")
    return attrs if isinstance(attrs, dict) else {}


def _observation_attributes(obs: dict[str, Any]) -> dict[str, Any]:
    metadata = obs.get("metadata")
    if not isinstance(metadata, dict):
        return {}
    attrs = metadata.get("attributes")
    return attrs if isinstance(attrs, dict) else {}


def _to_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _iso_to_ns(value: Any) -> int:
    """Best-effort ISO-8601 → ns conversion; returns 0 on failure.

    The TraceSpan domain shape expects nanoseconds for OTel parity;
    Langfuse returns ISO timestamps. Failing fast on parse errors
    would leak parser state into a domain shape; the engine reading
    spans is tolerant of zero-value timing fields at S7 (the field
    is mirrored from OTel for forward compatibility, not actively
    consumed). Real consumption arrives with the recommendation
    engine at P11 and the parser tightens then.
    """
    if not isinstance(value, str):
        return 0
    try:
        from datetime import datetime

        # Langfuse emits "Z" suffix; datetime.fromisoformat in 3.11+
        # handles it. Older Python paths replace "Z" with +00:00.
        normalised = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalised)
        return int(dt.timestamp() * 1_000_000_000)
    except ValueError:
        return 0
