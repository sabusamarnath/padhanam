"""collect_to_result — bridge AgentEvent stream to legacy AgentResult (D90, S29b).

The agent runtime's canonical observability surface at Phase 1 close
is the ``AgentEvent`` stream per D90. ``AgentResult`` remains as a
derived synchronous shape for callers that prefer a one-shot return
value (the integration test, the future CLI when it wants a final
result rather than rendering the stream, any non-streaming consumer
that arrives later).

``collect_to_result`` walks an ``AsyncIterator[AgentEvent]`` and
synthesises an ``AgentResult`` from the terminal event:

- ``InvocationCompleted``: clean termination; the result's content,
  cost, audit hashes, and termination reason come from the event's
  authoritative fields.
- ``InvariantBlocked``: invariant-block termination; result's
  termination_reason is ``INVARIANT_BLOCKED``; both audit hashes
  populated; content is the accumulated content deltas (which may be
  empty if the block fired before any content streamed).
- ``InvocationFailed``: unhandled-exception termination; result's
  termination_reason is ``ERROR``; audit hashes come from the
  variable-length ``partial_audit_chain_state`` (empty string for
  any hash that did not land before the failure).

If the stream ends without a terminal event, the helper raises
``EventStreamEndedWithoutTerminalError`` so callers can distinguish
this structural error from a clean ``ERROR`` termination.

The helper sits at the application layer because it composes domain
shapes (events from ``contexts/agent/domain/events.py``;
``AgentResult`` from ``contexts/agent/domain/agent_result.py``) into a
caller-shaped derivation; it does not itself participate in the
hexagonal port-and-adapter contract.
"""

from __future__ import annotations

from decimal import Decimal
from typing import AsyncIterator

from contexts.agent.domain.agent_result import AgentResult
from contexts.agent.domain.events import (
    AgentEvent,
    ContentDelta,
    InvariantBlocked,
    InvocationCompleted,
    InvocationFailed,
    IterationCompleted,
    IterationStarted,
)
from contexts.agent.domain.termination import TerminationReason


class EventStreamEndedWithoutTerminalError(RuntimeError):
    """Raised when an event stream ends without a terminal event (D90).

    Distinguishes the structural error ("the executor's stream did not
    yield one of the three terminal events before exhaustion") from a
    clean ``ERROR`` termination ("the executor emitted
    ``InvocationFailed`` to signal a failure"). Callers that care about
    debugging executor behaviour can catch this distinctly.
    """


async def collect_to_result(events: AsyncIterator[AgentEvent]) -> AgentResult:
    """Walk an ``AgentEvent`` stream and synthesise an ``AgentResult`` (D90).

    Accumulators (content fragments, iteration count, observed cost)
    track stream progress so non-clean terminations can surface a
    best-effort result. The terminal event's authoritative fields take
    precedence over accumulators for clean termination
    (``InvocationCompleted`` carries the canonical final cost and
    content); the accumulators carry the cost into the ``InvariantBlocked``
    and ``InvocationFailed`` paths where no authoritative total surfaces
    on the terminal event.
    """
    content_parts: list[str] = []
    cost_total: Decimal = Decimal("0")
    iteration_count: int = 0

    async for event in events:
        if isinstance(event, ContentDelta):
            content_parts.append(event.text_fragment)
            continue

        if isinstance(event, IterationStarted):
            # iteration_index is 1-based per D90; the count tracks the
            # highest index seen so a stream ending mid-iteration still
            # records the partial progress.
            if event.iteration_index > iteration_count:
                iteration_count = event.iteration_index
            continue

        if isinstance(event, IterationCompleted):
            cost_total += event.cost_usd
            continue

        if isinstance(event, InvocationCompleted):
            return AgentResult(
                response_content=event.final_result,
                signals=(),
                cost_total_usd=event.total_cost_usd,
                iteration_count=iteration_count or 1,
                termination_reason=event.termination_reason,
                audit_start_hash=event.audit_chain_hashes[0],
                audit_end_hash=event.audit_chain_hashes[1],
                early_termination=(
                    event.termination_reason is not TerminationReason.CONTENT
                ),
            )

        if isinstance(event, InvariantBlocked):
            return AgentResult(
                response_content="".join(content_parts),
                signals=(),
                cost_total_usd=cost_total,
                iteration_count=iteration_count or 1,
                termination_reason=TerminationReason.INVARIANT_BLOCKED,
                audit_start_hash=event.audit_chain_hashes[0],
                audit_end_hash=event.audit_chain_hashes[1],
                early_termination=True,
            )

        if isinstance(event, InvocationFailed):
            partial = event.partial_audit_chain_state
            return AgentResult(
                response_content="".join(content_parts),
                signals=(),
                cost_total_usd=cost_total,
                iteration_count=iteration_count,
                termination_reason=TerminationReason.ERROR,
                audit_start_hash=partial[0] if len(partial) >= 1 else "",
                audit_end_hash=partial[1] if len(partial) >= 2 else "",
                early_termination=True,
            )

        # Other intermediate events (LLMCallStarted, ToolCallProposed,
        # ToolCallExecuting, ToolCallCompleted, InvocationStarted) carry
        # iteration-local observability data; the synchronous AgentResult
        # shape does not expose them and collect_to_result discards them
        # in favour of the canonical event-stream surface.

    raise EventStreamEndedWithoutTerminalError(
        "agent event stream ended without yielding a terminal event "
        "(InvocationCompleted, InvariantBlocked, or InvocationFailed)"
    )


__all__ = ["collect_to_result", "EventStreamEndedWithoutTerminalError"]
