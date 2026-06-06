"""Google OIDC login settings — the first real identity provider (D161).

Platform-level config for the Google OpenID Connect login adapter
(``apps/api/_google_oidc.py``): the OAuth client credentials, the redirect
URI the callback route is reachable at, the standard Google OIDC endpoints
(provider defaults — the adapter is OIDC-generic, so Apple/Entra reuse its
shape with different endpoint config), and the operator email-to-tenant map
that scopes a verified Google identity to a tenant.

Secrets enter through this Settings subclass only — no module reads .env or
calls os.getenv directly (D19, enforced by import-linter). The client secret
and the operator email are never committed; they enter through the gitignored
.env. ``email_to_tenant`` is a JSON object in the env var (Pydantic parses
complex types from JSON), e.g.
``GOOGLE_OAUTH_EMAIL_TO_TENANT={"operator@example.com": "00000000-0000-4000-8000-00000000d001"}``.

The login carries identity scopes only (``openid email profile``); calendar
and mail data stay on the separate Nango path (D148). This is dogfooding-stack
login configuration, not the production IdP (the production auth path stays
the Keycloak swap, D3/D23).
"""

from __future__ import annotations

from padhanam.config.base import PadhanamSettings


class GoogleOAuthSettings(PadhanamSettings):
    """Google OIDC client + endpoints + operator email-to-tenant map (D161)."""

    # The OAuth client the operator created in the Google Cloud console.
    # Empty in the example env; the operator pastes the client id and secret.
    # ``is_configured`` is false (so the Google login is operator-gated and
    # the verifier raises) until both are present.
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    # The callback route the operator registers as the OAuth client's
    # authorized redirect URI. FastAPI serves /api/v1/auth/... directly; the
    # dogfooding stack publishes the API on http://localhost:8000, same-origin
    # with the login page.
    google_oauth_redirect_uri: str = (
        "http://localhost:8000/api/v1/auth/google/callback"
    )
    # Standard Google OIDC endpoints (provider defaults). The adapter is
    # OIDC-generic; these are configuration, not vendor specifics in code —
    # Apple/Entra supply their own endpoint set to the same adapter shape.
    google_oauth_auth_endpoint: str = (
        "https://accounts.google.com/o/oauth2/v2/auth"
    )
    google_oauth_token_endpoint: str = "https://oauth2.googleapis.com/token"
    google_oauth_jwks_uri: str = "https://www.googleapis.com/oauth2/v3/certs"
    # Google issues the ID token's ``iss`` as either form; both are accepted.
    google_oauth_issuers: tuple[str, ...] = (
        "https://accounts.google.com",
        "accounts.google.com",
    )
    # The operator email-to-tenant map. A verified Google email is resolved to
    # a tenant here; an email not in the map is rejected (no tenant fabricated,
    # no session minted). Empty by default — the operator sets the mapping in
    # .env. Lower-cased on lookup.
    google_oauth_email_to_tenant: dict[str, str] = {}

    @property
    def is_configured(self) -> bool:
        """True when the OAuth client is wired (id + secret both present)."""
        return bool(self.google_oauth_client_id and self.google_oauth_client_secret)
