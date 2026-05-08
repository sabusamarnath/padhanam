from __future__ import annotations

from padhanam.security.auth import Principal
from padhanam.security.policy import (
    OPERATOR_ROLE,
    Decision,
    Resource,
    check,
    is_operator,
)
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


# OPERATOR_ROLE and is_operator promoted from
# contexts/tenancy/application/use_cases.py to padhanam.security.policy
# at S23 commit 8 (D74). Tests below pin the constant and the
# predicate behaviour at the platform-level location.


def test_operator_role_constant_value() -> None:
    """The promoted constant preserves the original role string."""
    assert OPERATOR_ROLE == "padhanam.operator"


def test_is_operator_true_for_operator_principal() -> None:
    p = _principal("operator", [OPERATOR_ROLE])
    assert is_operator(p) is True


def test_is_operator_false_for_tenant_principal() -> None:
    p = _principal("tenant-a", ["audit.read", "audit.write"])
    assert is_operator(p) is False


def test_is_operator_false_for_principal_with_empty_roles() -> None:
    p = _principal("tenant-a", [])
    assert is_operator(p) is False


def test_is_operator_true_when_operator_role_alongside_other_roles() -> None:
    p = _principal("operator", [OPERATOR_ROLE, "audit.read"])
    assert is_operator(p) is True
