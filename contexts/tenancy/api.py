"""Public query interface for the tenancy context.

Per D17, every context exposes a single api.py at its root with read-
only query methods other contexts may call. Tenancy's read surface is
the use cases under ``contexts.tenancy.application`` re-exported here
so consumers depend on this module rather than reaching into
application internals. State-changing interactions (register, update)
flow through the same module — D17's "events for state changes"
direction is not yet wired in S10; cross-context subscriptions land
when consumers exist.
"""

from __future__ import annotations

from contexts.tenancy.application import (
    get_tenant,
    list_tenants,
    register_tenant,
    reveal_connection_config,
    update_tenant_status,
)

__all__ = [
    "get_tenant",
    "list_tenants",
    "register_tenant",
    "reveal_connection_config",
    "update_tenant_status",
]
