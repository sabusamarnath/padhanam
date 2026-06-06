"""Google OpenID Connect client — the OIDC mechanics behind the login port (D161).

S60b shipped the ``GoogleLoginVerifier`` seam assuming the ``credential`` was a
Google ID token already obtained client-side (one-tap / Google Identity
Services). The Step 0 reconciliation corrected that: the operator's setup is a
Google OAuth client with a redirect URI, i.e. a **server-side
authorization-code flow**. This module is the OIDC adapter that flow needs:

- ``authorization_url(state)`` — the URL the initiate route redirects to
  (``response_type=code``, ``openid email profile``, the signed ``state``).
- ``issue_state`` / ``verify_state`` — a signed, short-TTL state token (CSRF /
  replay guard). At single-operator allowlisted scale the email→tenant
  allowlist is the binding gate; browser-session-bound state defers to the
  multi-user identity package (D161).
- ``exchange_code_for_identity(code)`` — exchange the authorization code at
  Google's token endpoint, then verify the returned ID token (signature against
  Google's JWKS, ``aud``, ``iss``, ``exp``, ``email_verified``) and return the
  attested ``(subject, email)``.

The cryptographic verification is **PyJWT** (already a platform dependency — the
same library ``issue_dev_token`` uses); the code exchange and JWKS fetch are
**httpx** (already a dependency; tests inject an ``httpx.MockTransport``, the
calendar/email adapter precedent). No vendor SDK — the adapter is OIDC-generic,
Google's endpoints are configuration, so Apple/Entra reuse the shape (D161).
Every failure is raised as ``LoginError`` so the route maps it to 401 uniformly;
Google's live token contract is reconciled at the operator smoke, never asserted
from memory (the S4/S55a-fix discipline).
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt

from apps.api._auth_login_wiring import LoginError
from padhanam.config import GoogleOAuthSettings, SecuritySettings

_STATE_PURPOSE = "google_oauth_state"
_STATE_TTL = timedelta(minutes=10)
_SCOPES = "openid email profile"
_HTTP_TIMEOUT = 10.0


class GoogleOidcClient:
    """Google OIDC authorization-code client behind the login port (D161)."""

    def __init__(
        self,
        *,
        settings: GoogleOAuthSettings,
        state_signing_key: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._s = settings
        self._state_key = state_signing_key
        # Injected in tests (httpx.MockTransport serving the token + JWKS
        # endpoints); None in the running stack (real network egress).
        self._transport = transport

    @property
    def is_configured(self) -> bool:
        return self._s.is_configured

    # ------------------------------------------------------------- initiate
    def issue_state(self) -> str:
        """Mint a signed, short-TTL state token for the OAuth round-trip."""
        now = datetime.now(timezone.utc)
        return jwt.encode(
            {
                "purpose": _STATE_PURPOSE,
                "nonce": secrets.token_urlsafe(16),
                "iat": now,
                "exp": now + _STATE_TTL,
            },
            self._state_key,
            algorithm="HS256",
        )

    def verify_state(self, state: str) -> None:
        """Verify the state token (signature + freshness), or raise LoginError."""
        if not state:
            raise LoginError("missing oauth state")
        try:
            claims = jwt.decode(state, self._state_key, algorithms=["HS256"])
        except jwt.PyJWTError as exc:
            raise LoginError("invalid or expired oauth state") from exc
        if claims.get("purpose") != _STATE_PURPOSE:
            raise LoginError("oauth state has the wrong purpose")

    def authorization_url(self, *, state: str) -> str:
        """The Google authorization URL the initiate route redirects to."""
        params = {
            "client_id": self._s.google_oauth_client_id,
            "redirect_uri": self._s.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": _SCOPES,
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
        return f"{self._s.google_oauth_auth_endpoint}?{urlencode(params)}"

    # ------------------------------------------------------------- callback
    async def exchange_code_for_identity(self, code: str) -> tuple[str, str]:
        """Exchange the auth code and verify the ID token → (subject, email)."""
        if not self._s.is_configured:
            raise LoginError(
                "google login is operator-gated: set GOOGLE_OAUTH_CLIENT_ID "
                "and GOOGLE_OAUTH_CLIENT_SECRET in .env and reconcile the "
                "contract at the live smoke (D161)"
            )
        if not code:
            raise LoginError("missing authorization code")
        async with httpx.AsyncClient(
            transport=self._transport, timeout=_HTTP_TIMEOUT
        ) as client:
            id_token = await self._exchange_code(client, code)
            jwks = await self._fetch_jwks(client)
        return self._verify_id_token(id_token, jwks)

    async def _exchange_code(self, client: httpx.AsyncClient, code: str) -> str:
        try:
            resp = await client.post(
                self._s.google_oauth_token_endpoint,
                data={
                    "code": code,
                    "client_id": self._s.google_oauth_client_id,
                    "client_secret": self._s.google_oauth_client_secret,
                    "redirect_uri": self._s.google_oauth_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
        except httpx.HTTPError as exc:
            raise LoginError(f"google token exchange failed: {exc}") from exc
        if resp.status_code != 200:
            raise LoginError(
                f"google token exchange rejected the code (status {resp.status_code})"
            )
        try:
            id_token = resp.json()["id_token"]
        except (ValueError, KeyError) as exc:
            raise LoginError("google token response carried no id_token") from exc
        if not id_token:
            raise LoginError("google token response carried an empty id_token")
        return id_token

    async def _fetch_jwks(self, client: httpx.AsyncClient) -> dict[str, object]:
        try:
            resp = await client.get(self._s.google_oauth_jwks_uri)
        except httpx.HTTPError as exc:
            raise LoginError(f"could not fetch google signing keys: {exc}") from exc
        if resp.status_code != 200:
            raise LoginError(
                f"google signing-key endpoint returned status {resp.status_code}"
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise LoginError("google signing-key response was not JSON") from exc

    def _verify_id_token(
        self, id_token: str, jwks: dict[str, object]
    ) -> tuple[str, str]:
        try:
            header = jwt.get_unverified_header(id_token)
        except jwt.PyJWTError as exc:
            raise LoginError("malformed google id token") from exc
        kid = header.get("kid")
        key_jwk = self._select_key(jwks, kid)
        try:
            signing_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key_jwk))
        except Exception as exc:  # noqa: BLE001 — any malformed JWK → LoginError
            raise LoginError("could not build the google signing key") from exc
        try:
            claims = jwt.decode(
                id_token,
                signing_key,
                algorithms=["RS256"],
                audience=self._s.google_oauth_client_id,
                # Google issues ``iss`` in two forms; verified manually below.
                options={"verify_iss": False},
            )
        except jwt.ExpiredSignatureError as exc:
            raise LoginError("google id token has expired") from exc
        except jwt.InvalidAudienceError as exc:
            raise LoginError("google id token audience mismatch") from exc
        except jwt.PyJWTError as exc:
            raise LoginError("google id token failed verification") from exc
        if claims.get("iss") not in self._s.google_oauth_issuers:
            raise LoginError("google id token issuer mismatch")
        if not claims.get("email_verified"):
            raise LoginError("google account email is not verified")
        subject = claims.get("sub")
        email = claims.get("email")
        if not subject or not email:
            raise LoginError("google id token carried no subject/email")
        return str(subject), str(email)

    @staticmethod
    def _select_key(jwks: dict[str, object], kid: object) -> dict[str, object]:
        keys = jwks.get("keys")
        if not isinstance(keys, list) or not keys:
            raise LoginError("google signing-key set was empty")
        for key in keys:
            if isinstance(key, dict) and key.get("kid") == kid:
                return key
        raise LoginError("no google signing key matched the id token")


def build_google_oidc(
    *,
    settings: GoogleOAuthSettings | None = None,
    security: SecuritySettings | None = None,
) -> GoogleOidcClient | None:
    """Wire the Google OIDC client, or None when the OAuth client is unconfigured.

    None means the Google login is operator-gated (no client id/secret in
    .env); the initiate/callback routes 503 and the verifier raises until the
    operator wires the OAuth client and runs the live smoke (D161).
    """
    cfg = settings or GoogleOAuthSettings()
    if not cfg.is_configured:
        return None
    sec = security or SecuritySettings()
    return GoogleOidcClient(
        settings=cfg, state_signing_key=sec.auth_token_signing_key
    )


__all__ = ["GoogleOidcClient", "build_google_oidc"]
