"""AuditPort: outbound port for emitting audit events (D22).

Adapters implement this port. P2 ships a no-op adapter for use in S6/S7;
the real Postgres adapter lands in P3 with the tenant registry.

S12 widens emit to a coroutine. Audit emission sits inside the async
adapter call paths (registry mutations, tenant-scoped request handlers)
that already own an event loop, and the Postgres-backed adapter writes
through asyncpg. Sync emit-from-sync-context is a non-requirement at
P3 close; if a sync caller emerges later it dispatches through
``asyncio.run`` at the call site.

S27b (D88) widens ``emit``'s return type from ``None`` to ``AuditEvent``:
the Postgres adapter is the chain authority and recomputes hashes
inside its locking transaction (D37), so the persisted event carries
authoritative ``previous_event_hash`` and ``this_event_hash`` that
the caller (the agent runtime) needs to surface on ``AgentResult``.
Existing callers that ignore the return value continue to work.
"""

from __future__ import annotations

from typing import Protocol

from contexts.audit.domain.events import AuditEvent, ChainVerificationResult
from shared_kernel import TenantId


class AuditPort(Protocol):
    async def emit(self, event: AuditEvent) -> AuditEvent: ...

    async def verify_chain(
        self, tenant_id: TenantId
    ) -> ChainVerificationResult: ...
