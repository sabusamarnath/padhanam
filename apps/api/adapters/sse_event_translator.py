"""Translate AgentEvent values to SSE wire format (D90, S29b).

Per D90's transport-neutral domain placement: the AgentEvent vocabulary
at ``contexts/agent/domain/events.py`` is what the agent runtime emits.
The SSE transport lives at apps/api/ as an adapter that translates each
event to the SSE wire shape — ``event:`` line with the event type's
name, ``data:`` line with a JSON-serialized event payload, terminating
double newline per the W3C EventSource spec.

The translator is pure (no I/O); the route handler wraps it in
``StreamingResponse`` for the FastAPI side. Adding a WebSocket or gRPC
transport at Phase 2 touches only the adapter layer, not the runtime
or the event types themselves — this is what D90 sub-choice 4 commits.

JSON serialization handles: UUID → string, Decimal → string, datetime →
ISO format, Enum → value, TenantContext → nested dict via dataclasses.
The encoder is deliberately strict (no fallback to ``repr``); a missing
serializer indicates a new event field that the wire format must
explicitly support, which the test suite will catch.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from contexts.agent.domain.events import AgentEvent


def translate_event_to_sse(event: AgentEvent) -> str:
    """Translate one ``AgentEvent`` to its SSE wire-format string.

    Returns the full SSE block including event type, data, and the
    terminating double newline. Bytes encoding happens at the
    StreamingResponse boundary.
    """
    event_type_name = type(event).__name__
    payload = _serialize_event_payload(event)
    data_json = json.dumps(payload, separators=(",", ":"))
    return f"event: {event_type_name}\ndata: {data_json}\n\n"


def _serialize_event_payload(event: AgentEvent) -> dict[str, Any]:
    """Convert an event dataclass to a JSON-safe dict."""
    raw = dataclasses.asdict(event)
    return _json_safe(raw)


def _json_safe(value: Any) -> Any:
    """Recursively replace non-JSON-native types with their string forms."""
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


__all__ = ["translate_event_to_sse"]
