"""DTOs for the login token-exchange surface (D160, S60b)."""

from __future__ import annotations

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """A sign-in credential to exchange for a platform token.

    ``credential`` is the dev passphrase (dev backend) or a Google ID token
    (google backend). ``tenant_id`` is an optional dev-only override
    (guarded by the passphrase) for exercising a specific tenant.
    """

    credential: str
    tenant_id: str | None = None


class LoginResponse(BaseModel):
    """The issued platform token plus the identity it was issued for."""

    token: str
    subject: str
    email: str
    tenant_id: str


__all__ = ["LoginRequest", "LoginResponse"]
