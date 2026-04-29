"""AuditPort: outbound port for emitting audit events (D22).

Adapters implement this port. P2 ships a no-op adapter for use in S6/S7;
the real Postgres adapter lands in P3 with the tenant registry.
"""

from __future__ import annotations

from typing import Protocol

from contexts.audit.domain.events import AuditEvent, ChainVerificationResult
from shared_kernel import TenantId


class AuditPort(Protocol):
    def emit(self, event: AuditEvent) -> None: ...

    def verify_chain(self, tenant_id: TenantId) -> ChainVerificationResult: ...
