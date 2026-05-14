"""AuditDestination — read-side destination selector (D102, S36).

The audit read port routes to one of two destinations through a
parameter on each call rather than two ports per destination per
D102 alternative (b). The two destinations share the
``tenant_audit`` schema column-for-column per D35 and live on
distinct Postgres instances:

- ``per_tenant`` — the per-tenant ``tenant_audit`` table on the
  tenant's data plane. Requires a ``TenantContext`` at call time.
- ``control_plane`` — the control-plane ``tenant_audit`` table on
  the dedicated control-plane Postgres instance. The
  ``tenant_id`` column carries the empty-string sentinel per D35.
  Prohibits a ``TenantContext`` at call time.

Routing mismatches (per-tenant without context, control-plane
with context) raise ``AuditQueryRoutingError`` at port-method
entry per D102.
"""

from __future__ import annotations

from typing import Literal


AuditDestination = Literal["per_tenant", "control_plane"]


__all__ = ["AuditDestination"]
