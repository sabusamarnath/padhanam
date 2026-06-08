"""Unit tests for `apps.api.middleware.get_platform_operator_principal`
and the discriminator-check extension to `get_tenant_context` (D103, S37
commit 2).

The middleware dependency is tested as a function over a stub Request
because constructing a full FastAPI app for these checks would be heavy
relative to the surface tested.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from apps.api._auth_errors import PrincipalTypeMismatchError
from apps.api.middleware import get_actor_context, get_platform_operator_principal
from padhanam.security import PlatformOperatorPrincipal, Principal, PrincipalType
from shared_kernel import ActorContext, TenantId
from shared_kernel.authorisation import (
    DAILY_DRIVER_COMMITMENT_COMPLETE,
    DAILY_DRIVER_COMMITMENT_CREATE,
    DAILY_DRIVER_COMMITMENT_OBSERVE,
    DAILY_DRIVER_GOAL_RAISE_TARGET,
    DAILY_DRIVER_GOAL_READ,
    DAILY_DRIVER_ASSESSMENT_READ,
    DAILY_DRIVER_SUGGESTIONS_READ,
    DAILY_DRIVER_TODAY_READ,
    DAILY_DRIVER_TODAY_WRITE,
    DAILY_DRIVER_UNITS_CORRELATE,
    DAILY_DRIVER_UNITS_READ,
    INTAKE_RECORD_CREATE,
    INTAKE_RECORD_GET,
    INTAKE_RECORD_LIST,
    MESSAGING_MESSAGE_GET,
    MESSAGING_MESSAGE_LIST,
    MESSAGING_MESSAGE_RECEIVE,
    MESSAGING_MESSAGE_SEND,
    MESSAGING_PENDING_CLARIFICATION_CREATE,
    MESSAGING_PENDING_CLARIFICATION_EXPIRE,
    MESSAGING_PENDING_CLARIFICATION_RESOLVE,
    PORTFOLIO_CASE_CREATE,
    PORTFOLIO_CASE_GET,
    PORTFOLIO_CASE_LIST,
    PORTFOLIO_DATA_POINT_CREATE,
    PORTFOLIO_DATA_POINT_REVISE,
)

_TENANT_UUID = "00000000-0000-4000-8000-0000000000a1"


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
    the registered handler at _auth_errors.py (D104, S38) translates
    to 403 + AUTHZ_DENIAL security event."""
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


# --------------------------------------------------------------------
# get_actor_context (D126, S44a).
# --------------------------------------------------------------------


class _FakeRegistry:
    """Minimal tenant registry returning one fixed tenant row."""

    def __init__(self, tenant: object | None) -> None:
        self._tenant = tenant

    async def get_tenant(self, tenant_id: object) -> object | None:
        return self._tenant


def _request_with_registry(registry: _FakeRegistry) -> SimpleNamespace:
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(tenant_registry=registry)),
        state=SimpleNamespace(),
    )


def _tenant_principal() -> Principal:
    return Principal(
        subject="operator",
        tenant_id=TenantId(_TENANT_UUID),
        roles=frozenset({"audit.read"}),
        credential_ref="abc12345...",
        principal_type=PrincipalType.TENANT,
    )


def test_get_actor_context_builds_actor_context_from_principal_and_registry() -> None:
    """D126: get_actor_context composes the registry-resolved
    TenantContext with the Principal-derived actor identity."""
    tenant = SimpleNamespace(
        id=_TENANT_UUID, jurisdiction="UK", cost_attribution_id="cost-1"
    )
    request = _request_with_registry(_FakeRegistry(tenant))

    actor = asyncio.run(
        get_actor_context(request, principal=_tenant_principal())  # type: ignore[arg-type]
    )

    assert isinstance(actor, ActorContext)
    assert actor.actor_id == "operator"
    assert actor.tenant_context.tenant_id == _TENANT_UUID
    assert actor.tenant_context.jurisdiction == "UK"
    assert actor.tenant_context.cost_attribution_id == "cost-1"


def test_get_actor_context_populates_role_list_with_operator() -> None:
    """Phase 2-A single-role scope: role_list is the hardcoded
    {"operator"} frozenset."""
    tenant = SimpleNamespace(
        id=_TENANT_UUID, jurisdiction="UK", cost_attribution_id="cost-1"
    )
    request = _request_with_registry(_FakeRegistry(tenant))

    actor = asyncio.run(
        get_actor_context(request, principal=_tenant_principal())  # type: ignore[arg-type]
    )

    assert actor.role_list == frozenset({"operator"})
    assert isinstance(actor.role_list, frozenset)


def test_get_actor_context_resolves_the_phase_2a_permissions() -> None:
    """The hardcoded policy populates authorisation_set with the five
    portfolio permissions, the three intake permissions (D127), the
    four messaging permissions (D129), and the three PendingClarification
    permissions (D134) for the operator role."""
    tenant = SimpleNamespace(
        id=_TENANT_UUID, jurisdiction="UK", cost_attribution_id="cost-1"
    )
    request = _request_with_registry(_FakeRegistry(tenant))

    actor = asyncio.run(
        get_actor_context(request, principal=_tenant_principal())  # type: ignore[arg-type]
    )

    assert actor.authorisation_set == frozenset(
        {
            PORTFOLIO_CASE_CREATE,
            PORTFOLIO_CASE_LIST,
            PORTFOLIO_CASE_GET,
            PORTFOLIO_DATA_POINT_CREATE,
            PORTFOLIO_DATA_POINT_REVISE,
            INTAKE_RECORD_CREATE,
            INTAKE_RECORD_GET,
            INTAKE_RECORD_LIST,
            MESSAGING_MESSAGE_SEND,
            MESSAGING_MESSAGE_RECEIVE,
            MESSAGING_MESSAGE_GET,
            MESSAGING_MESSAGE_LIST,
            MESSAGING_PENDING_CLARIFICATION_CREATE,
            MESSAGING_PENDING_CLARIFICATION_RESOLVE,
            MESSAGING_PENDING_CLARIFICATION_EXPIRE,
            DAILY_DRIVER_TODAY_READ,
            DAILY_DRIVER_TODAY_WRITE,
            DAILY_DRIVER_COMMITMENT_CREATE,
            DAILY_DRIVER_COMMITMENT_COMPLETE,
            DAILY_DRIVER_COMMITMENT_OBSERVE,
            DAILY_DRIVER_GOAL_READ,
            DAILY_DRIVER_GOAL_RAISE_TARGET,
            DAILY_DRIVER_UNITS_READ,
            DAILY_DRIVER_UNITS_CORRELATE,
            DAILY_DRIVER_ASSESSMENT_READ,
            DAILY_DRIVER_SUGGESTIONS_READ,
        }
    )


def test_get_actor_context_rejects_platform_operator_principal() -> None:
    """Tenant-typed principals only: the platform-operator rejection is
    inherited from get_tenant_context's discriminator check (D103)."""
    platform_operator = Principal(
        subject="ops-1",
        tenant_id=TenantId(""),
        roles=frozenset(),
        credential_ref="def56789...",
        principal_type=PrincipalType.PLATFORM_OPERATOR,
    )
    request = _request_with_registry(_FakeRegistry(None))

    with pytest.raises(PrincipalTypeMismatchError):
        asyncio.run(
            get_actor_context(request, principal=platform_operator)  # type: ignore[arg-type]
        )
