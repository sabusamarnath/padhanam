"""TerminationReason — why an agent invocation stopped (D88, D90).

Relocated from ``contexts/agent/ports/executor.py`` at S29b to keep the
domain layer self-contained: the event types at
``contexts/agent/domain/events.py`` reference ``TerminationReason`` on
the ``InvocationCompleted`` event, and domain modules may not import
from ``contexts/agent/ports/`` per the hexagonal layering. The
``ports.executor`` module re-exports the symbol so existing callers
continue to work unchanged.

Strings rather than opaque ints so audit-row payloads, AgentResult
instances, and the new AgentEvent stream are human-readable end-to-end.
Subclassing ``str`` keeps comparison against literal strings ergonomic
for callers that haven't imported the Enum.
"""

from __future__ import annotations

from enum import Enum


class TerminationReason(str, Enum):
    CONTENT = "content"
    MAX_ITERATIONS = "max_iterations"
    TOOL_NOT_REGISTERED = "tool_not_registered"
    INVARIANT_BLOCKED = "invariant_blocked"
    ERROR = "error"
