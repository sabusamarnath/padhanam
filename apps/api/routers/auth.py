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

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from apps.api._auth_login_wiring import LoginError, LoginVerifier
from apps.api.routers._auth_dto import LoginRequest, LoginResponse
from padhanam.security.auth import issue_dev_token

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
ui_router = APIRouter(tags=["auth-ui"])

_PAGE_PATH = Path(__file__).resolve().parent.parent / "static" / "login.html"


def get_login_verifier(request: Request) -> LoginVerifier:
    """FastAPI dependency: the configured login verifier."""
    value = getattr(request.app.state, "login_verifier", None)
    if value is None:
        raise HTTPException(
            status_code=503,
            detail="login_verifier not configured on this API instance",
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


@ui_router.get("/", include_in_schema=False)
async def root_page() -> FileResponse:
    """Serve the login page at the root (the user-facing entry)."""
    return FileResponse(_PAGE_PATH, media_type="text/html")


@ui_router.get("/login", include_in_schema=False)
async def login_page() -> FileResponse:
    """Serve the login page (auth-exempt bytes; it posts to the login route)."""
    return FileResponse(_PAGE_PATH, media_type="text/html")


__all__ = ["router", "ui_router"]
