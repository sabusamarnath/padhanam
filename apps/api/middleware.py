"""Authentication middleware (D23).

Sits in front of every route — including 404 handlers and validation
error handlers — because it is added via app.add_middleware on the
FastAPI app object. Starlette processes middleware before routing,
so an unmatched path still runs through the middleware first and
gets a 401 if unauthenticated, only falling through to 404 once the
principal is established.

The dev backend (HS256 signed tokens) is sourced from
padhanam.security.auth (S5). The production swap is profile selection
plus a different SecuritySettings.auth_backend; the middleware code
does not change.

Failures emit a security event in the AUTH_FAILURE category (D26)
so SOC 2 / ISO 27001 evidence collection has a structured stream
distinct from application logs.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from padhanam.observability import (
    SecurityEvent,
    SecurityEventCategory,
    SecurityEventLogger,
    file_security_event_logger,
)
from padhanam.security import AuthError, Principal, verify_credential


# Routes that bypass authentication. The set is deliberately tiny and
# explicit — every other route, including unmatched paths, requires a
# valid credential. /health is the operator probe Caddy hits.
_PUBLIC_PATHS: frozenset[str] = frozenset({"/health"})


class AuthenticationMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Callable[..., Awaitable[Response]],
        *,
        security_event_logger: SecurityEventLogger | None = None,
    ) -> None:
        super().__init__(app)
        self._security_event_logger = (
            security_event_logger or file_security_event_logger()
        )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        credential = _extract_bearer(request)
        if credential is None:
            self._emit_failure(
                request, reason="missing_bearer", principal_ref=None
            )
            return JSONResponse(
                {"detail": "authentication required"}, status_code=401
            )

        try:
            principal = verify_credential(credential)
        except AuthError as e:
            self._emit_failure(
                request,
                reason=f"invalid_credential: {e}",
                principal_ref=credential[:8] + "...",
            )
            return JSONResponse(
                {"detail": "invalid credential"}, status_code=401
            )

        request.state.principal = principal
        return await call_next(request)

    def _emit_failure(
        self,
        request: Request,
        *,
        reason: str,
        principal_ref: str | None,
    ) -> None:
        self._security_event_logger.emit(
            SecurityEvent(
                category=SecurityEventCategory.AUTH_FAILURE,
                principal_ref=principal_ref,
                tenant_id=None,
                action=f"{request.method} {request.url.path}",
                resource_ref=None,
                outcome="denied",
                metadata={"reason": reason},
            )
        )


def _extract_bearer(request: Request) -> str | None:
    header = request.headers.get("authorization")
    if not header:
        return None
    parts = header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def get_principal(request: Request) -> Principal:
    """FastAPI dependency that returns the authenticated Principal.

    The middleware sets request.state.principal on every authenticated
    request; this helper is the canonical accessor. Routes that depend
    on it are guaranteed by the architecture (auth middleware in front
    of every route) to receive a valid Principal.
    """
    principal: Principal = request.state.principal
    return principal
