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
from typing import TYPE_CHECKING, Protocol

from padhanam.config import GoogleOAuthSettings, SecuritySettings

if TYPE_CHECKING:
    from apps.api._google_oidc import GoogleOidcClient


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


class OperatorEmailTenantResolver:
    """Maps a verified Google email to a tenant from the configured map (D161).

    The map is operator-set in ``.env``
    (``GOOGLE_OAUTH_EMAIL_TO_TENANT``); an email not in the map resolves to
    ``None`` so the verifier rejects it (no tenant fabricated, no session
    minted). Lookup is case-insensitive on the email.
    """

    def __init__(self, *, settings: GoogleOAuthSettings | None = None) -> None:
        cfg = settings or GoogleOAuthSettings()
        self._map = {
            email.lower(): tenant
            for email, tenant in cfg.google_oauth_email_to_tenant.items()
        }

    def resolve(self, email: str) -> str | None:
        return self._map.get(email.lower())


class GoogleLoginVerifier:
    """Google OIDC login behind the ``LoginVerifier`` port (D161).

    The Step 0 reconciliation reshaped the S60b seam: the ``credential`` is the
    OAuth **authorization code** (the server-side code flow), not a
    client-obtained ID token. ``verify`` exchanges the code and verifies the
    ID token through the OIDC adapter (``GoogleOidcClient``), then resolves the
    attested email to a tenant. The port method is unchanged — this is one
    adapter behind the existing port, not a parallel auth path.

    Operator-gated: with no OIDC client wired (no OAuth client configured in
    ``.env``), ``verify`` raises a descriptive ``LoginError`` rather than
    asserting Google's contract from memory (the S4/S55a-fix discipline). The
    live token contract is reconciled at the operator smoke.
    """

    def __init__(
        self,
        *,
        oidc: GoogleOidcClient | None = None,
        tenant_resolver: OperatorEmailTenantResolver | None = None,
    ) -> None:
        self._oidc = oidc
        self._resolver = tenant_resolver

    async def verify(
        self, *, credential: str, tenant_id: str | None = None
    ) -> VerifiedIdentity:
        if (
            self._oidc is None
            or not self._oidc.is_configured
            or self._resolver is None
        ):
            raise LoginError(
                "google login is operator-gated: wire the Google OAuth client "
                "(GOOGLE_OAUTH_CLIENT_ID / _SECRET) and the email→tenant map in "
                ".env and reconcile the contract at the live smoke (D161)"
            )
        subject, email = await self._oidc.exchange_code_for_identity(credential)
        resolved = self._resolver.resolve(email)
        if resolved is None:
            raise LoginError(f"no tenant mapped for {email!r}")
        return VerifiedIdentity(
            subject=subject, email=email, tenant_id=resolved, roles=("operator",)
        )


def build_login_verifier(
    *,
    settings: SecuritySettings | None = None,
    oidc: GoogleOidcClient | None = None,
) -> LoginVerifier:
    """Select the login verifier from config (dev wired; google needs an OIDC client).

    The dev passphrase verifier is the wired default for the dogfooding/test
    stack. With ``login_backend=google`` the Google OIDC verifier is returned;
    it is operator-gated until the OAuth client is configured (``oidc`` built
    by ``build_google_oidc``).
    """
    cfg = settings or SecuritySettings()
    if cfg.login_backend == "google":
        return build_google_login_verifier(oidc=oidc)
    return DevPassphraseLoginVerifier(settings=cfg)


def build_google_login_verifier(
    *, oidc: GoogleOidcClient | None
) -> GoogleLoginVerifier:
    """The Google OIDC verifier composed with the operator email→tenant resolver."""
    return GoogleLoginVerifier(
        oidc=oidc, tenant_resolver=OperatorEmailTenantResolver()
    )


__all__ = [
    "DevPassphraseLoginVerifier",
    "GoogleLoginVerifier",
    "LoginError",
    "LoginVerifier",
    "OperatorEmailTenantResolver",
    "VerifiedIdentity",
    "build_google_login_verifier",
    "build_login_verifier",
]
