from __future__ import annotations

from padhanam.security.auth import Principal
from padhanam.security.policy import Decision, Resource, check
from shared_kernel import TenantId


def _principal(tenant: str, roles: list[str]) -> Principal:
    return Principal(
        subject="alice",
        tenant_id=TenantId(tenant),
        roles=frozenset(roles),
        credential_ref="dev-token...",
    )


def test_allow_in_tenant_with_role() -> None:
    p = _principal("tenant-a", ["audit.read"])
    r = Resource(type="audit_event", id="e1", tenant_id=TenantId("tenant-a"))
    assert check(p, "audit.read", r) is Decision.ALLOW


def test_deny_cross_tenant() -> None:
    p = _principal("tenant-a", ["audit.read"])
    r = Resource(type="audit_event", id="e1", tenant_id=TenantId("tenant-b"))
    assert check(p, "audit.read", r) is Decision.DENY


def test_deny_missing_role() -> None:
    p = _principal("tenant-a", ["audit.read"])
    r = Resource(type="audit_event", id="e1", tenant_id=TenantId("tenant-a"))
    assert check(p, "audit.write", r) is Decision.DENY


def test_global_resource_allows_in_role() -> None:
    p = _principal("tenant-a", ["system.health"])
    r = Resource(type="health", id="ping", tenant_id=None)
    assert check(p, "system.health", r) is Decision.ALLOW
