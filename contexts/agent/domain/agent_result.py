"""AgentResult — the legacy synchronous shape derived from event streams (D90, S29b).

Per D90, the runtime's canonical observability surface is the
``AgentEvent`` stream at ``contexts/agent/domain/events.py``. ``AgentResult``
remains as a derived value for callers that prefer a synchronous shape:
the integration test, the future CLI (S30b) when it wants a one-shot
result, and any non-streaming consumer that arrives later. The
``collect_to_result`` helper at ``contexts/agent/application/collect.py``
walks an event stream and synthesises an ``AgentResult`` from the
terminal event.

Relocated from ``contexts/agent/ports/executor.py`` at S29b to keep the
domain layer self-contained (the ``AgentExecutor`` Protocol now yields
events, not results, so the data shape no longer belongs at the ports
layer). The ports module re-exports the symbol so existing callers
continue to work.

``AgentSignal`` rides along here as the legacy observability shape from
S27b (D88). With ``AgentEvent`` now the canonical surface, ``AgentSignal``
is preserved for backward compatibility but new consumers should
branch on ``AgentEvent`` types instead. ``AgentResult.signals`` is
left in place on the dataclass; ``collect_to_result`` populates it
with an empty tuple (the event stream carries the equivalent
information at higher fidelity).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping

from contexts.agent.domain.termination import TerminationReason


@dataclass(frozen=True)
class AgentSignal:
    """A structured signal emitted during an agent invocation (D88; legacy at D90).

    Observability surface, not control surface. The Phase 1 kinds
    (``tool_invoked``, ``retrieval_performed``, ``iteration_started``,
    ``iteration_completed``, ``invariant_blocked``,
    ``unregistered_tool_attempted``, ``max_iterations_terminated``)
    are preserved on this dataclass for backward compatibility with
    callers that consume ``AgentResult.signals``. New consumers should
    branch on ``AgentEvent`` types at the domain layer instead.
    """

    kind: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class AgentResult:
    """Output of a single agent invocation (D88; derived at D90).

    ``cost_total_usd`` is a Decimal to preserve precision; the
    aggregate sums per-LLM-call costs captured via OTel spans tagged
    with ``gen_ai.cost.*`` attributes per D49. The two audit hashes
    (``audit_start_hash``, ``audit_end_hash``) are the
    ``this_event_hash`` values from the AuditEvents emitted at
    invocation start and end per D26; callers can use them to deep-
    link into the audit chain or to verify chain integrity for the
    invocation.

    ``early_termination`` is True when the invocation hit the max-
    iterations cap (D88 conventional 10), terminated due to an
    unknown-tool branch, or was blocked by a platform invariant per
    D82 / D89; False on clean ``content`` termination.

    Per D90, ``signals`` is populated as an empty tuple by the
    ``collect_to_result`` helper at the application layer; the
    canonical observability surface is the ``AgentEvent`` stream.
    """

    response_content: str
    signals: tuple[AgentSignal, ...]
    cost_total_usd: Decimal
    iteration_count: int
    termination_reason: TerminationReason
    audit_start_hash: str
    audit_end_hash: str
    early_termination: bool = False
    metadata: dict[str, str] = field(default_factory=dict)
