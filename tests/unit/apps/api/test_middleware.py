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
from fastapi import HTTPException

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


def test_get_platform_operator_principal_rejects_tenant_principal_with_403() -> None:
    p = Principal(
        subject="alice",
        tenant_id=TenantId("tenant-a"),
        roles=frozenset({"audit.read"}),
        credential_ref="def56789...",
        principal_type=PrincipalType.TENANT,
    )
    with pytest.raises(HTTPException) as exc_info:
        get_platform_operator_principal(_request_with_principal(p))  # type: ignore[arg-type]
    assert exc_info.value.status_code == 403
    assert "platform_operator" in str(exc_info.value.detail)
    assert "tenant" in str(exc_info.value.detail)
