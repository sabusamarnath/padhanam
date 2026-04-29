"""Example tenant isolation contract test against the no-op audit adapter.

Necessarily trivial because the no-op adapter has no durable state; the
purpose is to establish the fixture pattern and red-team shape that real
adapters will follow in P3+.

Pattern: arrange two principals, attempt a cross-tenant operation as
principal A targeting tenant B's resource, assert the policy DENIES the
operation. Real adapters will additionally assert that even an
authorization bug (forced through with a manufactured ALLOW) cannot
leak data, by adapter-level tenant-scoped queries.
"""

from __future__ import annotations

from platform.security.auth import Principal
from platform.security.policy import Decision, Resource, check
from shared_kernel import TenantId


def test_principal_a_cannot_read_tenant_b_audit_event(
    tenant_a_principal: Principal,
) -> None:
    cross_tenant_resource = Resource(
        type="audit_event",
        id="event-from-tenant-b",
        tenant_id=TenantId("tenant-b"),
    )
    decision = check(tenant_a_principal, "audit.read", cross_tenant_resource)
    assert decision is Decision.DENY


def test_principal_b_cannot_write_to_tenant_a_audit_chain(
    tenant_b_principal: Principal,
) -> None:
    cross_tenant_resource = Resource(
        type="audit_event",
        id="event-from-tenant-a",
        tenant_id=TenantId("tenant-a"),
    )
    decision = check(tenant_b_principal, "audit.write", cross_tenant_resource)
    assert decision is Decision.DENY


def test_principal_can_read_own_tenant_audit_event(
    tenant_a_principal: Principal,
) -> None:
    own_resource = Resource(
        type="audit_event",
        id="event-own",
        tenant_id=TenantId("tenant-a"),
    )
    decision = check(tenant_a_principal, "audit.read", own_resource)
    assert decision is Decision.ALLOW
