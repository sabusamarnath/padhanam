"""Authentication interface (D23).

Dev backend verifies HS256-signed tokens with a key from SecuritySettings.
Production backend resolves the auth backend selector to a Keycloak adapter
that validates RS256 tokens against the IdP's published keys (D3, D23);
the production swap is configuration, not refactor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import jwt

from platform.config import AuthBackend, SecuritySettings
from shared_kernel import TenantId

ALGORITHM = "HS256"


class AuthError(Exception):
    """Raised when a credential cannot be verified."""


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: TenantId
    roles: frozenset[str]
    credential_ref: str = field(repr=False)


def issue_dev_token(
    subject: str, tenant_id: str, roles: list[str]
) -> str:
    """Issue a dev-only signed token. Test fixtures only — no production use."""
    settings = SecuritySettings()
    payload = {
        "sub": subject,
        "tenant_id": tenant_id,
        "roles": roles,
    }
    return jwt.encode(payload, settings.auth_token_signing_key, algorithm=ALGORITHM)


def verify_credential(credential: str) -> Principal:
    """Verify a credential and return the resulting Principal.

    Raises AuthError on any verification failure; never returns None for the
    invalid case (callers must catch, and the auth middleware turns AuthError
    into a 401 with a security event emitted).
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
        tenant_id = payload["tenant_id"]
        roles = payload.get("roles", [])
    except KeyError as e:
        raise AuthError(f"credential missing required claim: {e}") from e

    return Principal(
        subject=subject,
        tenant_id=TenantId(tenant_id),
        roles=frozenset(roles),
        credential_ref=credential[:8] + "...",
    )
