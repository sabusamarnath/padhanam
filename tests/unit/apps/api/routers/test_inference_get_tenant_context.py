"""Unit tests for the D103 discriminator-check extension to
`apps.api.routers.inference.get_tenant_context` (S37 commit 2).

The extension rejects platform-operator-typed principals with HTTP 403
before any registry resolution; tenant-typed principals continue to
flow through the existing 503/400/404 paths unchanged.

Full registry-resolution coverage stays in the integration tier; these
tests narrow on the new discriminator branch.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from apps.api._errors import PrincipalTypeMismatchError
from apps.api.routers.inference import get_tenant_context
from padhanam.security import Principal, PrincipalType
from shared_kernel import TenantId


def _request_with_app_state(**state) -> SimpleNamespace:
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(**state)),
        state=SimpleNamespace(),
    )


def test_get_tenant_context_rejects_platform_operator_with_typed_error() -> None:
    """D103: platform-operator tokens raise PrincipalTypeMismatchError;
    the registered handler at _errors.py translates to 403 + AUTHZ_DENIAL
    security event."""
    p = Principal(
        subject="ops-1",
        tenant_id=TenantId(""),
        roles=frozenset(),
        credential_ref="abc12345...",
        principal_type=PrincipalType.PLATFORM_OPERATOR,
    )
    # The discriminator check fires before any state access; the
    # request app state need not carry a tenant_registry for this
    # branch.
    request = _request_with_app_state(tenant_registry=None)
    with pytest.raises(PrincipalTypeMismatchError) as exc_info:
        asyncio.run(get_tenant_context(request, principal=p))  # type: ignore[arg-type]
    assert exc_info.value.required == "tenant"
    assert exc_info.value.actual == "platform_operator"


def test_get_tenant_context_503_when_registry_missing_for_tenant_principal() -> None:
    """Existing 503 path stays unchanged for tenant-typed principals."""
    p = Principal(
        subject="alice",
        tenant_id=TenantId("00000000-0000-0000-0000-000000000001"),
        roles=frozenset({"audit.read"}),
        credential_ref="def56789...",
        principal_type=PrincipalType.TENANT,
    )
    request = _request_with_app_state(tenant_registry=None)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_tenant_context(request, principal=p))  # type: ignore[arg-type]
    assert exc_info.value.status_code == 503
    assert "registry" in str(exc_info.value.detail).lower()
