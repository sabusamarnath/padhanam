"""No-op audit adapter for P2 use.

Emits the event as a structured log line at INFO level so call sites are
debuggable in S6/S7. Chain verification is not yet implementable (no
durable store), so it raises. Real Postgres adapter lands in P3 with the
tenant registry.
"""

from __future__ import annotations

import logging

from contexts.audit.domain.events import AuditEvent, ChainVerificationResult
from shared_kernel import TenantId

_log = logging.getLogger("contexts.audit.noop")


class NoOpAuditAdapter:
    async def emit(self, event: AuditEvent) -> None:
        _log.info(
            "audit_event tenant=%s actor=%s action=%s resource=%s/%s hash=%s",
            event.tenant_id,
            event.actor,
            event.action_verb,
            event.resource_type,
            event.resource_id,
            event.this_event_hash[:12],
        )

    async def verify_chain(self, tenant_id: TenantId) -> ChainVerificationResult:
        raise NotImplementedError(
            "Chain verification requires durable storage. Real adapter "
            "lands in P3 with the tenant registry."
        )
