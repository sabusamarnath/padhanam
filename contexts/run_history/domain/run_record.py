"""RunRecord — the structured run record domain value object (D95, S31).

Fifteen-column shape matching the ``runs`` per-tenant table from
D95. The frozen dataclass is the in-process projection of the
canonical audit chain over the agent runtime's terminal events
per D94; the writer adapter persists instances to the per-tenant
database, and the read-side query port (S33) returns instances
back to Phase 2 UX.

Invariants enforced in ``__post_init__`` mirror the migration's
schema-layer CHECK constraints so the domain object refuses
inconsistent inputs at construction time without round-tripping
through the database. Six invariants land at S31 commit 2:

1. ``tenant_id`` non-empty (mirrors ``runs.tenant_id <> ''``).
2. ``jurisdiction`` non-empty.
3. ``iteration_count >= 0`` (mirrors the schema CHECK).
4. ``total_cost_usd >= Decimal("0")`` (mirrors the schema CHECK).
5. Hash fields are 64 lowercase hex characters. ``audit_start_hash``
   is always required; ``audit_end_hash`` is required EXCEPT when
   ``termination_reason == 'failed'`` (the 1-hash
   ``InvocationFailed.partial_audit_chain_state`` case from the
   executor, per D95).
6. ``completed_at >= started_at`` (catches clock-skew and test-
   fixture errors at the domain layer; no schema CHECK enforces this
   pair because Postgres CHECK on two columns is awkward).
7. ``termination_reason`` ∈ the six-value set per D95: the five
   ``TerminationReason`` enum values plus the synthesised
   ``failed`` value for the ``InvocationFailed`` terminal event
   class which carries no ``termination_reason`` field of its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


# Six values per D95: the five TerminationReason enum values plus
# synthesised `failed` for InvocationFailed terminal events. The
# synthesis is the runs-row-only mapping; the executor's domain
# enum at contexts/agent/domain/termination.py is unchanged.
TERMINATION_REASONS: frozenset[str] = frozenset({
    "content",
    "max_iterations",
    "tool_not_registered",
    "error",
    "invariant_blocked",
    "failed",
})


_HEX_CHARS: frozenset[str] = frozenset("0123456789abcdef")


def _is_64_hex(value: str) -> bool:
    if len(value) != 64:
        return False
    return all(c in _HEX_CHARS for c in value)


@dataclass(frozen=True)
class RunRecord:
    """Structured run record projection over the audit chain (D95).

    Frozen — immutable post-construction so callers cannot mutate
    a record between assembly in ``invoke_agent`` and persistence
    through the writer adapter. Field order matches the column
    order in ``charter/schema.md``'s ``runs`` table for grep-
    friendly cross-reference.
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

    def __post_init__(self) -> None:
        if not self.tenant_id:
            raise ValueError("tenant_id must be non-empty")
        if not self.jurisdiction:
            raise ValueError("jurisdiction must be non-empty")
        if self.iteration_count < 0:
            raise ValueError(
                f"iteration_count must be >= 0; got {self.iteration_count}"
            )
        if self.total_cost_usd < Decimal("0"):
            raise ValueError(
                f"total_cost_usd must be >= 0; got {self.total_cost_usd}"
            )
        if not _is_64_hex(self.audit_start_hash):
            raise ValueError(
                "audit_start_hash must be 64 lowercase hex characters"
            )
        if self.audit_end_hash is not None and not _is_64_hex(self.audit_end_hash):
            raise ValueError(
                "audit_end_hash must be 64 lowercase hex characters or None"
            )
        if self.audit_end_hash is None and self.termination_reason != "failed":
            raise ValueError(
                "audit_end_hash may be None only when termination_reason='failed' "
                f"(got termination_reason={self.termination_reason!r}); "
                "the chain-incomplete state is reserved for the 1-hash "
                "InvocationFailed case per D95"
            )
        if self.completed_at < self.started_at:
            raise ValueError(
                "completed_at must be >= started_at; "
                f"got started_at={self.started_at.isoformat()} "
                f"completed_at={self.completed_at.isoformat()}"
            )
        if self.termination_reason not in TERMINATION_REASONS:
            raise ValueError(
                f"termination_reason must be one of {sorted(TERMINATION_REASONS)}; "
                f"got {self.termination_reason!r}"
            )
