"""RunHistoryWriter consumer port + AgentRunRecord DTO (D17, D94, D95, S31).

The agent runtime's consumer-side port for persisting the run
record after the terminal event yields per D95's write-timing
commitment (shape B). The wiring adapter at
``apps/cli/_cross_context.py`` translates the ``AgentRunRecord``
DTO defined here into the run-history domain object
(``contexts.run_history.domain.RunRecord``) and calls
``contexts.run_history.api.record_run``.

D5 / D17 consumer-defined-ports precedent: the agent context
defines the shape it needs from the run-history producer context;
the producer exposes its use case at ``api.py``; the wiring
adapter joins them at the application composition layer. The
agent context's domain and application layers never import from
``contexts.run_history``. The AST test at
``tests/unit/contexts/agent/application/ports/test_run_history_writer.py``
plus the import-linter ``Cross-context: application layers are
independent`` contract together enforce the boundary.

The DTO mirrors the 15-column ``RunRecord`` shape from D95 one-
for-one at the type level. The structural duplication is the
intentional cost of the D17 boundary; the wiring adapter does
field-for-field translation. Future consumers that need
different consumer-shapes define their own DTOs at their
context's port boundary.

This port is the fifth consumer-port-plus-wiring-adapter port at
the agent context (after MethodologyLookup, RoleLookup,
MethodologyOverridesLookup, AgentRetrievalClient,
ToolDefinitionsLookup, ToolInvoker, SourceLookup). The pattern
continues its altitude-agnostic shape from the S29b captures
entry; the same shape lifts from cross-context (this) through
intra-context wiring through transport adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from padhanam.security import Principal


@dataclass(frozen=True)
class AgentRunRecord:
    """Agent-context-shaped run record DTO (D95).

    Frozen dataclass mirroring the 15-column shape from D95's
    ``runs`` table. Field order matches the ``charter/schema.md``
    column order for grep-friendly cross-reference. The wiring
    adapter at ``apps/cli/_cross_context.py`` translates instances
    of this DTO into ``contexts.run_history.domain.RunRecord`` and
    persists through the run-history context's ``record_run``
    use case.

    No validation invariants land on this DTO; the producer-side
    ``RunRecord`` domain object enforces them at construction
    time inside the wiring adapter. The agent context's role is
    to assemble the field values from the in-flight event stream
    per D95's audit-chain partial-state mapping; the producer
    domain object is the structural-correctness boundary.

    ``audit_end_hash`` is nullable; ``invoke_agent``'s assembly
    logic sets it to None for the 1-hash InvocationFailed case
    per D95's write-time mapping.
    """

    id: UUID
    tenant_id: str
    jurisdiction: str
    agent_template_id: UUID
    agent_template_version: int
    input_message: str
    output_content: str
    started_at: datetime
    completed_at: datetime
    termination_reason: str
    iteration_count: int
    total_cost_usd: Decimal
    trace_id: str | None
    audit_start_hash: str
    audit_end_hash: str | None
    created_at: datetime


class RunHistoryWriter(Protocol):
    """Async port for persisting a single run record (D94, D95).

    The agent context's ``invoke_agent`` use case calls this
    after yielding the terminal event from the executor's stream
    per D95's write-timing commitment (shape B). The wiring
    adapter at ``apps/cli/_cross_context.py`` translates the
    ``AgentRunRecord`` DTO into the run-history domain object
    and persists via the run-history context's ``record_run``
    use case.

    Auth posture matches the agent-context port convention: the
    Protocol takes ``principal`` so the underlying use case can
    perform the D75-style ``_is_authenticated`` check at the
    producer side. The runtime caller is the tenant-context
    principal threaded through ``invoke_agent``.

    Returns ``None`` on success; raises on persistence failure.
    Per D95's write-timing reasoning, writer failure raises after
    the terminal event has yielded to the SSE client; the
    missing-row condition is reconcilable from the audit chain
    via ``audit_end_hash`` at Phase 2 UX consumption time.

    Pre-condition imposed by ``invoke_agent`` (not by this port):
    ``InvocationFailed`` events with empty
    ``partial_audit_chain_state`` are skipped before reaching
    this port. The writer only sees invocations with audit
    evidence per D95's projection-over-recorded-activity framing.
    """

    async def record_run(
        self,
        record: AgentRunRecord,
        *,
        principal: Principal,
    ) -> None: ...
