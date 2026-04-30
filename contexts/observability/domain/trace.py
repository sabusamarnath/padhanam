"""Trace value objects for the observability read path.

Domain models for the recommendation engine's view of trace history.
The shape is OTel-aligned (so consumption from any OTel-consuming
backend is uniform) but vendor-free: domain code never imports
langfuse, OTel SDKs, or HTTP clients (D16, D27).

The recommendation engine work that consumes these lands when the
P3 tenant registry exists. The S7 surface is the port shape and a
no-op adapter; domain types are scaffolded so the engine can land
without re-shaping the read path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TraceSpan:
    """One span in a queried trace.

    Mirrors OTel span fields without importing the OTel SDK so the
    domain stays portable. Attributes carry the GenAI semantic-
    convention values the recommendation engine reads.
    """

    span_id: str
    parent_span_id: str | None
    name: str
    start_time_ns: int
    end_time_ns: int
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TraceRecord:
    """A trace as the read path returns it.

    `tenant_id` is the tenant the trace belongs to (jurisdiction
    flows alongside in production, resolved by the tenant registry).
    Spans are unordered; the engine traverses by parent_span_id.
    """

    trace_id: str
    tenant_id: str
    spans: list[TraceSpan]
