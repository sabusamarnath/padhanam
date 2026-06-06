"""Login token-exchange routes (D160, S60b).

- ``POST /api/v1/auth/login`` — exchange a sign-in credential for the
  platform JWT the data routes require. Public (you cannot bearer-auth the
  act of logging in); the credential is the gate, the issued token carries
  the tenant scope. Closes the paste-a-dev-token UX backdoor (S58).
- ``GET /`` and ``GET /login`` — serve the login page (public bytes; it
  posts to the route above and stores the returned token).

The data routes stay bearer-authed throughout — this surface only changes
how the operator obtains the token. The ``LoginVerifier`` is the seam: the
dev adapter is wired for the dogfooding stack; the Google adapter is
operator-gated (D160).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from apps.api._auth_login_wiring import LoginError, LoginVerifier
from apps.api._google_oidc import GoogleOidcClient
from apps.api.routers._auth_dto import LoginRequest, LoginResponse
from padhanam.security.auth import issue_dev_token

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
ui_router = APIRouter(tags=["auth-ui"])

_PAGE_PATH = Path(__file__).resolve().parent.parent / "static" / "login.html"


def get_login_verifier(request: Request) -> LoginVerifier:
    """FastAPI dependency: the configured login verifier (passphrase route)."""
    value = getattr(request.app.state, "login_verifier", None)
    if value is None:
        raise HTTPException(
            status_code=503,
            detail="login_verifier not configured on this API instance",
        )
    return value  # type: ignore[return-value]


def get_google_oidc(request: Request) -> GoogleOidcClient:
    """FastAPI dependency: the Google OIDC client, or 503 when operator-gated."""
    value = getattr(request.app.state, "google_oidc", None)
    if value is None or not value.is_configured:
        raise HTTPException(
            status_code=503,
            detail=(
                "google login is operator-gated: configure the Google OAuth "
                "client (GOOGLE_OAUTH_CLIENT_ID / _SECRET) and set "
                "LOGIN_BACKEND=google (D161)"
            ),
        )
    return value


def get_google_login_verifier(request: Request) -> LoginVerifier:
    """FastAPI dependency: the Google OIDC verifier the callback resolves through."""
    value = getattr(request.app.state, "google_login_verifier", None)
    if value is None:
        raise HTTPException(
            status_code=503,
            detail="google login is operator-gated: no Google verifier wired (D161)",
        )
    return value  # type: ignore[return-value]


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    verifier: Annotated[LoginVerifier, Depends(get_login_verifier)],
) -> LoginResponse:
    """Exchange a verified sign-in credential for a platform JWT."""
    try:
        identity = await verifier.verify(
            credential=body.credential, tenant_id=body.tenant_id
        )
    except LoginError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    token = issue_dev_token(
        subject=identity.subject,
        tenant_id=identity.tenant_id,
        roles=list(identity.roles),
    )
    return LoginResponse(
        token=token,
        subject=identity.subject,
        email=identity.email,
        tenant_id=identity.tenant_id,
    )


@router.get("/google/initiate", include_in_schema=False)
async def google_initiate(
    oidc: Annotated[GoogleOidcClient, Depends(get_google_oidc)],
) -> RedirectResponse:
    """Start the Google OIDC flow — redirect to Google with a signed state (D161)."""
    state = oidc.issue_state()
    return RedirectResponse(oidc.authorization_url(state=state), status_code=302)


@router.get("/google/callback", include_in_schema=False)
async def google_callback(
    oidc: Annotated[GoogleOidcClient, Depends(get_google_oidc)],
    verifier: Annotated[LoginVerifier, Depends(get_google_login_verifier)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    """Google OIDC callback: verify state, exchange the code, mint the JWT (D161).

    Ends in a small HTML bridge that stores the token under the same
    ``dd_token`` key the passphrase path uses and lands in ``/app`` — the
    Google-minted session is byte-identical to the passphrase-minted one at
    the bearer-authed data routes (a browser redirect cannot return JSON for
    the page JS to store, so the bridge carries it).
    """
    if error:
        return _bridge_error(f"Google sign-in was cancelled or failed ({error}).")
    if not code or not state:
        return _bridge_error("Google sign-in returned no authorization code.")
    try:
        oidc.verify_state(state)
        identity = await verifier.verify(credential=code)
    except LoginError as exc:
        return _bridge_error(str(exc))
    token = issue_dev_token(
        subject=identity.subject,
        tenant_id=identity.tenant_id,
        roles=list(identity.roles),
    )
    return _bridge_success(token)


def _bridge_success(token: str) -> HTMLResponse:
    """Store the minted JWT under ``dd_token`` and redirect to the app shell."""
    payload = json.dumps(token)  # safe embed (server-minted JWT, no user input)
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Signing you in…</title></head><body>"
        "<p>Signing you in…</p><script>"
        f"localStorage.setItem('dd_token', {payload});"
        "window.location.replace('/app');"
        "</script></body></html>"
    )
    return HTMLResponse(html)


def _bridge_error(message: str) -> HTMLResponse:
    """Land back on the login page carrying the failure reason."""
    payload = json.dumps(message)
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Sign-in failed</title></head><body>"
        "<p>Sign-in failed. Returning to sign in…</p><script>"
        f"sessionStorage.setItem('dd_login_error', {payload});"
        "window.location.replace('/login');"
        "</script></body></html>"
    )
    return HTMLResponse(html, status_code=401)


@ui_router.get("/", include_in_schema=False)
async def root_page() -> FileResponse:
    """Serve the login page at the root (the user-facing entry)."""
    return FileResponse(_PAGE_PATH, media_type="text/html")


@ui_router.get("/login", include_in_schema=False)
async def login_page() -> FileResponse:
    """Serve the login page (auth-exempt bytes; it posts to the login route)."""
    return FileResponse(_PAGE_PATH, media_type="text/html")


__all__ = ["router", "ui_router"]
