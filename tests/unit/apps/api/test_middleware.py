"""Unit tests for `apps.api.middleware.get_platform_operator_principal`
and the discriminator-check extension to `get_tenant_context` (D103, S37
commit 2).

The middleware dependency is tested as a function over a stub Request
because constructing a full FastAPI app for these checks would be heavy
relative to the surface tested.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from apps.api._errors import PrincipalTypeMismatchError
from apps.api.middleware import get_platform_operator_principal
from padhanam.security import PlatformOperatorPrincipal, Principal, PrincipalType
from shared_kernel import TenantId


def _request_with_principal(principal: Principal) -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(principal=principal))


def test_get_platform_operator_principal_accepts_platform_operator_principal() -> None:
    p = Principal(
        subject="ops-1",
        tenant_id=TenantId(""),
        roles=frozenset(),
        credential_ref="abc12345...",
        principal_type=PrincipalType.PLATFORM_OPERATOR,
    )
    result = get_platform_operator_principal(_request_with_principal(p))  # type: ignore[arg-type]
    assert isinstance(result, PlatformOperatorPrincipal)
    assert result.subject == "ops-1"
    assert result.credential_ref == "abc12345..."


def test_get_platform_operator_principal_rejects_tenant_principal_with_typed_error() -> None:
    """D103: tenant tokens raise the typed PrincipalTypeMismatchError;
    the registered handler at _errors.py translates to 403 + AUTHZ_DENIAL
    security event."""
    p = Principal(
        subject="alice",
        tenant_id=TenantId("tenant-a"),
        roles=frozenset({"audit.read"}),
        credential_ref="def56789...",
        principal_type=PrincipalType.TENANT,
    )
    with pytest.raises(PrincipalTypeMismatchError) as exc_info:
        get_platform_operator_principal(_request_with_principal(p))  # type: ignore[arg-type]
    assert exc_info.value.required == "platform_operator"
    assert exc_info.value.actual == "tenant"
