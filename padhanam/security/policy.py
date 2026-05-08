"""Authorization interface (D23).

Dev backend: ALLOW iff principal's tenant matches the resource's tenant
*and* the principal carries a role permitting the action. Production
backend resolves to a policy-as-code engine (OPA-shaped) configured per
tenant; the production swap is configuration, not refactor.

Every check emits a security event (D26). The logger is wired in by
``padhanam.observability.security_events`` rather than imported here so
this module stays a leaf of the padhanam import graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

from padhanam.security.auth import Principal
from shared_kernel import TenantId


# Platform-level operator role per D34. Promoted from
# ``contexts/tenancy/application/use_cases.py`` at S23 commit 8 so the
# methodology context can consume the predicate without a cross-context
# application-to-application import (D17). The role string is stable;
# the constant is the authoritative location.
OPERATOR_ROLE = "padhanam.operator"


def is_operator(principal: Principal) -> bool:
    """Operator-context predicate (D34).

    A principal is operator-context iff it carries the operator role.
    Tenant-context callers carry their own roles (e.g. ``"audit.read"``)
    but not this one. Use cases that mutate control-plane state guard
    on this predicate and raise ``AuthorizationError`` on
    tenant-context callers (mirroring ``reveal_connection_config``'s
    rejection path).
    """
    return OPERATOR_ROLE in principal.roles


class Decision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class AuthorizationError(Exception):
    """Raised when a use case rejects an authorization decision.

    Decisions are made by ``check()``; use cases that turn DENY into a
    raised exception (rather than a returned value) raise this. The
    auth middleware does not raise this directly; it returns 401 on
    auth failure (AuthError) or 403 on policy denial via use-case
    propagation.
    """


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
