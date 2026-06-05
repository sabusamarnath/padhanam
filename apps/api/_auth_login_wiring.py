"""Login surface composition — the token-exchange seam (D160, S60b).

S60 entered through the auth-exempt `/app` backdoor pasting a CLI-minted
dev token. S60b closes that UX: a login surface verifies a sign-in
credential through a ``LoginVerifier`` port and a route issues the
platform JWT the data routes already require (``issue_dev_token``,
reused). The data routes stay bearer-authed throughout — this seam only
changes how the operator *obtains* the token.

The dev adapter (``DevPassphraseLoginVerifier``) is the wired default for
the dogfooding stack: it verifies the configured passphrase and returns a
verified identity scoped to the configured tenant. The Google adapter
(``GoogleLoginVerifier``) is the production-shaped path (design-language
§9 one-tap), and it is **operator-gated**: verifying a real Google ID
token and mapping the email to a tenant are external-contract steps the
build environment cannot reach, so the adapter calls an injected verifier
the operator wires at deploy and raises a clear ``LoginError`` until then.
Asserting Google's token contract from memory is the S4/S55a-fix
anti-pattern; the seam is real, the vendor call is operator-provided.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol

from padhanam.config import SecuritySettings


class LoginError(Exception):
    """Raised when a sign-in credential cannot be verified (→ 401 at the route)."""


@dataclass(frozen=True)
class VerifiedIdentity:
    """The result of verifying a sign-in credential.

    Carries everything the token-exchange route needs to issue the
    platform JWT: the subject, the email (for display / audit), the
    tenant the identity is scoped to, and the roles to grant.
    """

    subject: str
    email: str
    tenant_id: str
    roles: tuple[str, ...]


class LoginVerifier(Protocol):
    """Verifies a sign-in credential and returns the verified identity."""

    async def verify(
        self, *, credential: str, tenant_id: str | None = None
    ) -> VerifiedIdentity:
        """Verify the credential or raise ``LoginError``."""
        ...


class DevPassphraseLoginVerifier:
    """Dev login: a configured passphrase → the configured tenant identity.

    The wired default for the dogfooding stack. The passphrase is the gate;
    a successful login maps to the configured subject + tenant + the
    operator role. Tests and the local loop run without .env edits via the
    SecuritySettings dev defaults. An explicit ``tenant_id`` (dev-only,
    guarded by the passphrase) overrides the configured tenant — useful for
    exercising tenant isolation in tests.
    """

    def __init__(self, *, settings: SecuritySettings | None = None) -> None:
        self._settings = settings or SecuritySettings()

    async def verify(
        self, *, credential: str, tenant_id: str | None = None
    ) -> VerifiedIdentity:
        if not credential or credential != self._settings.dev_login_passphrase:
            raise LoginError("invalid dev login credential")
        subject = self._settings.dev_login_subject
        resolved_tenant = tenant_id or self._settings.dev_login_tenant_id
        if not resolved_tenant:
            raise LoginError("no tenant configured for the dev login")
        return VerifiedIdentity(
            subject=subject,
            email=f"{subject}@dev.local",
            tenant_id=resolved_tenant,
            roles=("operator",),
        )


# An operator-provided verifier: given a Google ID token, return the
# (subject, email) it attests, or raise. The operator wires the real
# google-auth verification + audience check at deploy; the seam never
# assumes Google's token contract.
GoogleIdTokenVerifier = Callable[[str], Awaitable[tuple[str, str]]]


class GoogleLoginVerifier:
    """Google one-tap login (design-language §9) — operator-gated (D160).

    Verifies a Google ID token through an injected verifier and maps the
    attested email to a tenant through an injected resolver. Both are
    operator-provided at deploy (the live Google contract + the email→tenant
    mapping are external steps the build environment cannot reach). With
    neither wired, ``verify`` raises a descriptive ``LoginError`` rather
    than asserting Google's contract from memory.
    """

    def __init__(
        self,
        *,
        id_token_verifier: GoogleIdTokenVerifier | None = None,
        tenant_for_email: Callable[[str], Awaitable[str | None]] | None = None,
    ) -> None:
        self._verify_token = id_token_verifier
        self._tenant_for_email = tenant_for_email

    async def verify(
        self, *, credential: str, tenant_id: str | None = None
    ) -> VerifiedIdentity:
        if self._verify_token is None or self._tenant_for_email is None:
            raise LoginError(
                "google login is operator-gated: wire the Google ID-token "
                "verifier and the email→tenant resolver at deploy and "
                "reconcile the contract at the live smoke (D160)"
            )
        subject, email = await self._verify_token(credential)
        resolved = await self._tenant_for_email(email)
        if resolved is None:
            raise LoginError(f"no tenant for {email!r}")
        return VerifiedIdentity(
            subject=subject, email=email, tenant_id=resolved, roles=("operator",)
        )


def build_login_verifier(
    *, settings: SecuritySettings | None = None
) -> LoginVerifier:
    """Select the login verifier from config (dev wired; google operator-gated)."""
    cfg = settings or SecuritySettings()
    if cfg.login_backend == "google":
        return GoogleLoginVerifier()
    return DevPassphraseLoginVerifier(settings=cfg)


__all__ = [
    "DevPassphraseLoginVerifier",
    "GoogleIdTokenVerifier",
    "GoogleLoginVerifier",
    "LoginError",
    "LoginVerifier",
    "VerifiedIdentity",
    "build_login_verifier",
]
