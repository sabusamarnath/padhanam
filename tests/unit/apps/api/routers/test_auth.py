"""Tests for the login token-exchange surface (D160, S60b).

The dev login verifier (the wired default) and the POST /api/v1/auth/login
route: a valid passphrase exchanges for a platform JWT scoped to the
configured tenant; a bad credential is 401; the Google verifier is
operator-gated (raises until wired). The issued token verifies through the
existing auth backend, closing the loop with the bearer-authed data routes.
"""

from __future__ import annotations

import asyncio
import json
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api._auth_login_wiring import (
    DevPassphraseLoginVerifier,
    GoogleLoginVerifier,
    LoginError,
    OperatorEmailTenantResolver,
    build_login_verifier,
)
from apps.api.routers import auth as auth_router
from padhanam.config import GoogleOAuthSettings, SecuritySettings
from padhanam.security.auth import verify_credential

_TENANT = "00000000-0000-4000-8000-00000000d001"
_TENANT_B = "00000000-0000-4000-8000-00000000d002"
_OPERATOR_EMAIL = "operator@example.com"


def _settings(**over) -> SecuritySettings:
    base = dict(
        dev_login_passphrase="s3cret",
        dev_login_subject="operator",
        dev_login_tenant_id=_TENANT,
        login_backend="dev",
    )
    base.update(over)
    return SecuritySettings(**base)


# ---------------------------------------------------------------- verifier
def test_dev_verifier_accepts_passphrase_and_scopes_to_tenant() -> None:
    v = DevPassphraseLoginVerifier(settings=_settings())
    identity = asyncio.run(v.verify(credential="s3cret"))
    assert identity.subject == "operator"
    assert identity.tenant_id == _TENANT
    assert "operator" in identity.roles


def test_dev_verifier_rejects_bad_passphrase() -> None:
    v = DevPassphraseLoginVerifier(settings=_settings())
    with pytest.raises(LoginError):
        asyncio.run(v.verify(credential="wrong"))


def test_dev_verifier_allows_explicit_tenant_override() -> None:
    v = DevPassphraseLoginVerifier(settings=_settings())
    other = "00000000-0000-4000-8000-00000000a002"
    identity = asyncio.run(v.verify(credential="s3cret", tenant_id=other))
    assert identity.tenant_id == other


def test_google_verifier_is_operator_gated_until_wired() -> None:
    v = GoogleLoginVerifier()  # no injected verifier / resolver
    with pytest.raises(LoginError):
        asyncio.run(v.verify(credential="any-google-id-token"))


def test_build_login_verifier_selects_by_backend() -> None:
    assert isinstance(
        build_login_verifier(settings=_settings(login_backend="dev")),
        DevPassphraseLoginVerifier,
    )
    assert isinstance(
        build_login_verifier(settings=_settings(login_backend="google")),
        GoogleLoginVerifier,
    )


# ------------------------------------------------------------------- route
def _client(verifier) -> TestClient:
    app = FastAPI()
    app.include_router(auth_router.router)
    app.state.login_verifier = verifier
    return TestClient(app, raise_server_exceptions=False)


def test_login_route_issues_a_verifiable_token() -> None:
    client = _client(DevPassphraseLoginVerifier(settings=_settings()))
    res = client.post("/api/v1/auth/login", json={"credential": "s3cret"})
    assert res.status_code == 200
    body = res.json()
    assert body["tenant_id"] == _TENANT
    assert body["subject"] == "operator"
    # The issued token verifies through the platform auth backend and
    # carries the tenant scope the data routes require.
    principal = verify_credential(body["token"])
    assert str(principal.tenant_id) == _TENANT
    assert "operator" in principal.roles


def test_login_route_rejects_bad_credential_401() -> None:
    client = _client(DevPassphraseLoginVerifier(settings=_settings()))
    res = client.post("/api/v1/auth/login", json={"credential": "nope"})
    assert res.status_code == 401


def test_login_route_503_when_unconfigured() -> None:
    client = _client(None)
    res = client.post("/api/v1/auth/login", json={"credential": "x"})
    assert res.status_code == 503


# ----------------------------------------------- Google OIDC initiate/callback
class _FakeOidc:
    """A GoogleOidcClient stand-in for the route tests (no real Google call)."""

    def __init__(
        self,
        *,
        identity: tuple[str, str] = ("google-sub-1", _OPERATOR_EMAIL),
        configured: bool = True,
        good_state: str = "good-state",
    ) -> None:
        self._identity = identity
        self._configured = configured
        self._good_state = good_state

    @property
    def is_configured(self) -> bool:
        return self._configured

    def issue_state(self) -> str:
        return self._good_state

    def verify_state(self, state: str) -> None:
        if state != self._good_state:
            raise LoginError("invalid or expired oauth state")

    def authorization_url(self, *, state: str) -> str:
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}"

    async def exchange_code_for_identity(self, code: str) -> tuple[str, str]:
        if code == "boom":
            raise LoginError("google token exchange rejected the code")
        return self._identity


def _google_app(
    *,
    oidc: _FakeOidc | None,
    email_to_tenant: dict[str, str] | None = None,
) -> TestClient:
    app = FastAPI()
    app.include_router(auth_router.router)
    app.state.google_oidc = oidc
    if oidc is not None:
        resolver = OperatorEmailTenantResolver(
            settings=GoogleOAuthSettings(
                google_oauth_email_to_tenant=email_to_tenant
                or {_OPERATOR_EMAIL: _TENANT}
            )
        )
        app.state.google_login_verifier = GoogleLoginVerifier(
            oidc=oidc, tenant_resolver=resolver
        )
    else:
        app.state.google_login_verifier = None
    return TestClient(app, raise_server_exceptions=False)


def _token_from_bridge(html: str) -> str:
    match = re.search(r"setItem\('dd_token', (\".*?\")\)", html)
    assert match, f"no dd_token in bridge page: {html!r}"
    return json.loads(match.group(1))


def test_initiate_redirects_to_google() -> None:
    client = _google_app(oidc=_FakeOidc())
    res = client.get("/api/v1/auth/google/initiate", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"].startswith(
        "https://accounts.google.com/o/oauth2/v2/auth?"
    )


def test_callback_happy_path_mints_a_tenant_scoped_session() -> None:
    client = _google_app(oidc=_FakeOidc())
    res = client.get(
        "/api/v1/auth/google/callback",
        params={"code": "auth-code", "state": "good-state"},
    )
    assert res.status_code == 200
    assert "/app" in res.text
    token = _token_from_bridge(res.text)
    # The Google-minted session is byte-identical to the passphrase-minted one
    # at the bearer-authed data routes: it verifies through the same backend.
    principal = verify_credential(token)
    assert str(principal.tenant_id) == _TENANT
    assert "operator" in principal.roles


def test_callback_rejects_a_bad_state() -> None:
    client = _google_app(oidc=_FakeOidc())
    res = client.get(
        "/api/v1/auth/google/callback",
        params={"code": "auth-code", "state": "forged"},
    )
    assert res.status_code == 401
    assert "dd_token" not in res.text


def test_callback_surfaces_an_oauth_error_param() -> None:
    client = _google_app(oidc=_FakeOidc())
    res = client.get(
        "/api/v1/auth/google/callback",
        params={"error": "access_denied"},
    )
    assert res.status_code == 401
    assert "dd_token" not in res.text


def test_callback_rejects_an_unmapped_email_without_minting() -> None:
    client = _google_app(
        oidc=_FakeOidc(identity=("sub-x", "stranger@gmail.com")),
    )
    res = client.get(
        "/api/v1/auth/google/callback",
        params={"code": "auth-code", "state": "good-state"},
    )
    assert res.status_code == 401
    assert "dd_token" not in res.text


def test_callback_isolation_minted_session_carries_the_resolved_tenant() -> None:
    # Two operator emails mapped to two tenants; each callback mints a session
    # scoped to exactly its tenant — no cross-tenant leakage on the seam.
    mapping = {"a@gmail.com": _TENANT, "b@gmail.com": _TENANT_B}
    for email, expected in mapping.items():
        client = _google_app(
            oidc=_FakeOidc(identity=(f"sub-{email}", email)),
            email_to_tenant=mapping,
        )
        res = client.get(
            "/api/v1/auth/google/callback",
            params={"code": "auth-code", "state": "good-state"},
        )
        assert res.status_code == 200
        principal = verify_credential(_token_from_bridge(res.text))
        assert str(principal.tenant_id) == expected


def test_initiate_503_when_google_operator_gated() -> None:
    client = _google_app(oidc=None)
    res = client.get("/api/v1/auth/google/initiate", follow_redirects=False)
    assert res.status_code == 503


def test_callback_503_when_google_operator_gated() -> None:
    client = _google_app(oidc=None)
    res = client.get(
        "/api/v1/auth/google/callback",
        params={"code": "auth-code", "state": "good-state"},
    )
    assert res.status_code == 503
