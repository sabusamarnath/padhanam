"""Tests for the Google OIDC login adapter (D161, S60c).

The ``GoogleOidcClient`` mechanics with Google calls **mocked** via
``httpx.MockTransport`` (the calendar/email adapter precedent): the token
endpoint returns an RSA-signed ID token, the JWKS endpoint returns the
matching public key, and the adapter verifies signature / audience / issuer /
expiry / email_verified through PyJWT. The valid, expired, wrong-audience,
unverified-email, and issuer-mismatch paths are exercised, plus the token
exchange failure paths. ``OperatorEmailTenantResolver`` and the reshaped
``GoogleLoginVerifier`` (credential = authorization code) round out the unit.

MockTransport caveat (the S55a-fix discipline): these tests sign their own ID
tokens, so they verify the adapter *verifies a well-formed token correctly* —
they cannot verify what Google actually emits. The live operator smoke is the
gate for the real token contract.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.api._auth_login_wiring import (
    GoogleLoginVerifier,
    LoginError,
    OperatorEmailTenantResolver,
)
from apps.api._google_oidc import GoogleOidcClient, build_google_oidc
from padhanam.config import GoogleOAuthSettings

_CLIENT_ID = "test-client-id.apps.googleusercontent.com"
_KID = "test-kid-1"
_TENANT = "00000000-0000-4000-8000-00000000d001"
_OPERATOR_EMAIL = "operator@example.com"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"

# One 2048-bit keypair for the whole module — generating per-test is slow and
# the key material is irrelevant to what each test asserts.
_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwks() -> dict:
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(_PRIVATE_KEY.public_key()))
    jwk.update({"kid": _KID, "alg": "RS256", "use": "sig"})
    return {"keys": [jwk]}


def _id_token(**overrides) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "iss": "https://accounts.google.com",
        "aud": _CLIENT_ID,
        "sub": "google-subject-123",
        "email": _OPERATOR_EMAIL,
        "email_verified": True,
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    claims.update(overrides)
    return jwt.encode(
        claims, _PRIVATE_KEY, algorithm="RS256", headers={"kid": _KID}
    )


def _settings(**over) -> GoogleOAuthSettings:
    base = dict(
        google_oauth_client_id=_CLIENT_ID,
        google_oauth_client_secret="test-secret",
        google_oauth_email_to_tenant={_OPERATOR_EMAIL: _TENANT},
    )
    base.update(over)
    return GoogleOAuthSettings(**base)


def _client(id_token: str | None, *, token_status: int = 200) -> GoogleOidcClient:
    """A GoogleOidcClient whose Google endpoints are served by MockTransport."""

    def _handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == _TOKEN_URL:
            if token_status != 200:
                return httpx.Response(token_status, json={"error": "invalid_grant"})
            body = {} if id_token is None else {"id_token": id_token}
            return httpx.Response(200, json=body)
        if url == _JWKS_URL:
            return httpx.Response(200, json=_jwks())
        return httpx.Response(404)

    return GoogleOidcClient(
        settings=_settings(),
        state_signing_key="unit-state-signing-key",
        transport=httpx.MockTransport(_handler),
    )


# ----------------------------------------------------------- exchange + verify
def test_valid_id_token_yields_subject_and_email() -> None:
    client = _client(_id_token())
    subject, email = asyncio.run(client.exchange_code_for_identity("auth-code"))
    assert subject == "google-subject-123"
    assert email == _OPERATOR_EMAIL


def test_expired_id_token_is_rejected() -> None:
    now = datetime.now(timezone.utc)
    client = _client(_id_token(exp=now - timedelta(minutes=5), iat=now - timedelta(hours=1)))
    with pytest.raises(LoginError, match="expired"):
        asyncio.run(client.exchange_code_for_identity("auth-code"))


def test_wrong_audience_id_token_is_rejected() -> None:
    client = _client(_id_token(aud="some-other-client.apps.googleusercontent.com"))
    with pytest.raises(LoginError, match="audience"):
        asyncio.run(client.exchange_code_for_identity("auth-code"))


def test_unverified_email_id_token_is_rejected() -> None:
    client = _client(_id_token(email_verified=False))
    with pytest.raises(LoginError, match="not verified"):
        asyncio.run(client.exchange_code_for_identity("auth-code"))


def test_issuer_mismatch_id_token_is_rejected() -> None:
    client = _client(_id_token(iss="https://evil.example.com"))
    with pytest.raises(LoginError, match="issuer"):
        asyncio.run(client.exchange_code_for_identity("auth-code"))


def test_token_endpoint_rejection_is_a_login_error() -> None:
    client = _client(_id_token(), token_status=400)
    with pytest.raises(LoginError, match="rejected the code"):
        asyncio.run(client.exchange_code_for_identity("auth-code"))


def test_missing_id_token_in_response_is_a_login_error() -> None:
    client = _client(None)
    with pytest.raises(LoginError, match="no id_token"):
        asyncio.run(client.exchange_code_for_identity("auth-code"))


def test_unconfigured_client_is_operator_gated() -> None:
    client = GoogleOidcClient(
        settings=GoogleOAuthSettings(
            google_oauth_client_id="", google_oauth_client_secret=""
        ),
        state_signing_key="k",
    )
    with pytest.raises(LoginError, match="operator-gated"):
        asyncio.run(client.exchange_code_for_identity("auth-code"))


# ---------------------------------------------------------------- authz url
def test_authorization_url_carries_oidc_params() -> None:
    client = _client(_id_token())
    url = client.authorization_url(state="abc")
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "response_type=code" in url
    assert "scope=openid+email+profile" in url
    assert "state=abc" in url
    assert f"client_id={_CLIENT_ID}" in url


# -------------------------------------------------------------------- state
def test_state_round_trips() -> None:
    client = _client(_id_token())
    client.verify_state(client.issue_state())  # no raise


def test_tampered_state_is_rejected() -> None:
    client = _client(_id_token())
    with pytest.raises(LoginError):
        client.verify_state(client.issue_state() + "tamper")


def test_empty_state_is_rejected() -> None:
    client = _client(_id_token())
    with pytest.raises(LoginError):
        client.verify_state("")


# ------------------------------------------------------------ build_google_oidc
def test_build_google_oidc_is_none_until_configured() -> None:
    assert build_google_oidc(
        settings=GoogleOAuthSettings(
            google_oauth_client_id="", google_oauth_client_secret=""
        )
    ) is None
    assert isinstance(build_google_oidc(settings=_settings()), GoogleOidcClient)


# --------------------------------------------------- email-to-tenant resolver
def test_resolver_maps_configured_email_case_insensitively() -> None:
    resolver = OperatorEmailTenantResolver(settings=_settings())
    assert resolver.resolve(_OPERATOR_EMAIL) == _TENANT
    assert resolver.resolve(_OPERATOR_EMAIL.upper()) == _TENANT


def test_resolver_returns_none_for_unmapped_email() -> None:
    resolver = OperatorEmailTenantResolver(settings=_settings())
    assert resolver.resolve("stranger@gmail.com") is None


# ---------------------------------------------- GoogleLoginVerifier (the port)
def test_google_verifier_resolves_code_to_scoped_identity() -> None:
    verifier = GoogleLoginVerifier(
        oidc=_client(_id_token()),
        tenant_resolver=OperatorEmailTenantResolver(settings=_settings()),
    )
    identity = asyncio.run(verifier.verify(credential="auth-code"))
    assert identity.subject == "google-subject-123"
    assert identity.email == _OPERATOR_EMAIL
    assert identity.tenant_id == _TENANT
    assert identity.roles == ("operator",)


def test_google_verifier_rejects_unmapped_email() -> None:
    verifier = GoogleLoginVerifier(
        oidc=_client(_id_token(email="stranger@gmail.com")),
        tenant_resolver=OperatorEmailTenantResolver(settings=_settings()),
    )
    with pytest.raises(LoginError, match="no tenant mapped"):
        asyncio.run(verifier.verify(credential="auth-code"))


def test_google_verifier_operator_gated_without_oidc() -> None:
    verifier = GoogleLoginVerifier()  # nothing wired
    with pytest.raises(LoginError, match="operator-gated"):
        asyncio.run(verifier.verify(credential="auth-code"))
