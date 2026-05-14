"""Authentication interface (D23, D103).

Dev backend verifies HS256-signed tokens with a key from SecuritySettings.
Production backend resolves the auth backend selector to a Keycloak adapter
that validates RS256 tokens against the IdP's published keys (D3, D23);
the production swap is configuration, not refactor.

D103 (S37) extends the claim payload with a ``principal_type``
discriminator. Two values at Phase 1: ``"tenant"`` (the existing shape,
with ``tenant_id`` claim required) and ``"platform_operator"`` (new,
with no ``tenant_id``). The discriminator anchors ``tenant_id``'s
conditional validity at decode time; the existing ``roles`` claim
continues to carry permission markers within a principal type and is
not replaced by the discriminator (per D103 reasoning).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

import jwt

from padhanam.config import AuthBackend, SecuritySettings
from shared_kernel import TenantId

ALGORITHM = "HS256"


class AuthError(Exception):
    """Raised when a credential cannot be verified."""


class PrincipalType(StrEnum):
    """Categorical type of the authenticated principal (D103).

    ``TENANT`` — the existing shape; the principal is scoped to a
    tenant via the ``tenant_id`` claim.

    ``PLATFORM_OPERATOR`` — new at S37; the principal has no tenant
    scope and is authorised against control-plane resources (the
    control-plane audit chain). The token payload carries no
    ``tenant_id`` claim; ``Principal.tenant_id`` is set to the empty
    sentinel ``TenantId("")`` for consumer-side convenience (downstream
    code that accesses ``principal.tenant_id`` should first check
    ``principal.principal_type`` per D103 layering).
    """

    TENANT = "tenant"
    PLATFORM_OPERATOR = "platform_operator"


# Sentinel for platform-operator principals. Per D103, platform-operator
# tokens carry no ``tenant_id`` claim; downstream consumers that read
# ``principal.tenant_id`` for tenant-context purposes should first check
# the discriminator. Using an empty TenantId rather than ``Optional``
# keeps the dataclass surface minimal and the existing tenant-context
# consumer sites (which are pre-checked by the route layer) unchanged.
_PLATFORM_OPERATOR_TENANT_SENTINEL = TenantId("")


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: TenantId
    roles: frozenset[str]
    credential_ref: str = field(repr=False)
    principal_type: PrincipalType = PrincipalType.TENANT


@dataclass(frozen=True)
class PlatformOperatorPrincipal:
    """Control-plane scope marker for platform-operator-typed principals (D103).

    Returned by ``apps.api.middleware.get_platform_operator_principal``.
    Routes that depend on this type are guaranteed by the dependency
    function to receive a principal whose token payload carried
    ``principal_type == "platform_operator"``.

    The thin shape carries the underlying principal's subject and
    ``credential_ref`` for security-event logging; no ``roles`` or
    ``tenant_id`` are surfaced because platform-operator-typed
    principals are control-plane-scoped by construction.
    """

    subject: str
    credential_ref: str = field(repr=False)


def issue_dev_token(
    subject: str,
    tenant_id: str,
    roles: list[str],
    *,
    principal_type: PrincipalType = PrincipalType.TENANT,
) -> str:
    """Issue a dev-only signed token. Test fixtures only — no production use.

    Default ``principal_type`` is ``TENANT`` so all existing
    issuance call sites continue to produce tenant-scoped tokens
    without modification. The ``tenant_id`` argument is required at
    the function signature for backwards compatibility; callers that
    issue platform-operator tokens should use
    ``issue_platform_operator_dev_token`` instead, which drops the
    parameter.
    """
    payload: dict[str, object] = {
        "sub": subject,
        "tenant_id": tenant_id,
        "roles": roles,
        "principal_type": principal_type.value,
    }
    settings = SecuritySettings()
    return jwt.encode(payload, settings.auth_token_signing_key, algorithm=ALGORITHM)


def issue_platform_operator_dev_token(
    subject: str,
    roles: list[str] | None = None,
) -> str:
    """Issue a dev-only platform-operator token (D103, S37 commit 2).

    Platform-operator tokens carry ``principal_type == "platform_operator"``
    and no ``tenant_id`` claim. Per D103 alternative (j), the helper
    omits ``OPERATOR_ROLE`` by default; ``OPERATOR_ROLE`` gates
    tenant-scoped operator-context actions (audit test-event at S12,
    registry mutations at S10) where the operator acts on a named
    tenant, which is a distinct concept from platform-operator's
    control-plane scope.

    Tests that need both semantics mint a tenant-typed token with
    ``OPERATOR_ROLE`` plus a platform-operator-typed token, exercising
    the two surfaces separately.
    """
    payload: dict[str, object] = {
        "sub": subject,
        "roles": roles or [],
        "principal_type": PrincipalType.PLATFORM_OPERATOR.value,
    }
    settings = SecuritySettings()
    return jwt.encode(payload, settings.auth_token_signing_key, algorithm=ALGORITHM)


def verify_credential(credential: str) -> Principal:
    """Verify a credential and return the resulting Principal.

    Raises AuthError on any verification failure; never returns None
    for the invalid case (callers must catch, and the auth middleware
    turns AuthError into a 401 with a security event emitted).

    D103 conditional validation on ``tenant_id``:

    - ``principal_type == "tenant"`` (or unspecified — defaults to
      tenant for back-compat): ``tenant_id`` is required; missing
      raises ``AuthError``.
    - ``principal_type == "platform_operator"``: ``tenant_id`` is
      prohibited; present raises ``AuthError``. The decoded
      Principal's ``tenant_id`` is set to the empty sentinel
      (consumers must check the discriminator before relying on
      ``tenant_id``).
    """
    settings = SecuritySettings()
    if settings.auth_backend is not AuthBackend.DEV_SIGNED_TOKEN:
        raise AuthError(
            f"auth backend {settings.auth_backend!r} not implemented; "
            "production Keycloak adapter lands in P3 per D3/D23"
        )

    try:
        payload = jwt.decode(
            credential,
            settings.auth_token_signing_key,
            algorithms=[ALGORITHM],
        )
    except jwt.PyJWTError as e:
        raise AuthError(f"invalid credential: {e}") from e

    try:
        subject = payload["sub"]
    except KeyError as e:
        raise AuthError(f"credential missing required claim: {e}") from e

    raw_principal_type = payload.get("principal_type", PrincipalType.TENANT.value)
    try:
        principal_type = PrincipalType(raw_principal_type)
    except ValueError as e:
        raise AuthError(
            f"credential principal_type {raw_principal_type!r} is not "
            f"one of {[pt.value for pt in PrincipalType]}"
        ) from e

    roles = payload.get("roles", [])
    tenant_id_claim = payload.get("tenant_id")

    if principal_type is PrincipalType.TENANT:
        if tenant_id_claim is None:
            raise AuthError(
                "credential with principal_type='tenant' must carry a "
                "tenant_id claim"
            )
        tenant_id = TenantId(tenant_id_claim)
    else:
        if tenant_id_claim is not None:
            raise AuthError(
                "credential with principal_type='platform_operator' must "
                "not carry a tenant_id claim"
            )
        tenant_id = _PLATFORM_OPERATOR_TENANT_SENTINEL

    return Principal(
        subject=subject,
        tenant_id=tenant_id,
        roles=frozenset(roles),
        credential_ref=credential[:8] + "...",
        principal_type=principal_type,
    )
