"""Authorization interface (D23).

Dev backend: ALLOW iff principal's tenant matches the resource's tenant
*and* the principal carries a role permitting the action. Production
backend resolves to a policy-as-code engine (OPA-shaped) configured per
tenant; the production swap is configuration, not refactor.

Every check emits a security event (D26). The logger is wired in by
``platform.observability.security_events`` rather than imported here so
this module stays a leaf of the platform import graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

from platform.security.auth import Principal
from shared_kernel import TenantId


class Decision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True)
class Resource:
    """The thing being acted upon. Tenant-scoped resources carry tenant_id."""

    type: str
    id: str
    tenant_id: TenantId | None


# Hook for the security event logger to register itself. Wired in apps/.
# Callable signature: emit(principal, action, resource, decision) -> None.
_emit_hook: Callable[[Principal, str, Resource, Decision], None] | None = None


def register_emit_hook(
    hook: Callable[[Principal, str, Resource, Decision], None],
) -> None:
    global _emit_hook
    _emit_hook = hook


def check(principal: Principal, action: str, resource: Resource) -> Decision:
    """Resolve an authorization decision and emit a security event."""
    decision = _decide(principal, action, resource)
    if _emit_hook is not None:
        _emit_hook(principal, action, resource, decision)
    return decision


def _decide(principal: Principal, action: str, resource: Resource) -> Decision:
    if resource.tenant_id is not None and principal.tenant_id != resource.tenant_id:
        return Decision.DENY
    if action not in principal.roles:
        return Decision.DENY
    return Decision.ALLOW
