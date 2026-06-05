"""Tests for the login token-exchange surface (D160, S60b).

The dev login verifier (the wired default) and the POST /api/v1/auth/login
route: a valid passphrase exchanges for a platform JWT scoped to the
configured tenant; a bad credential is 401; the Google verifier is
operator-gated (raises until wired). The issued token verifies through the
existing auth backend, closing the loop with the bearer-authed data routes.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api._auth_login_wiring import (
    DevPassphraseLoginVerifier,
    GoogleLoginVerifier,
    LoginError,
    build_login_verifier,
)
from apps.api.routers import auth as auth_router
from padhanam.config import SecuritySettings
from padhanam.security.auth import verify_credential

_TENANT = "00000000-0000-4000-8000-00000000d001"


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
