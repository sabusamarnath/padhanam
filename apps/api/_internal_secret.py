"""Internal-secret authentication for the HTTP trigger endpoint (D145, D147, S54).

The trigger endpoint at ``POST /api/v1/internal/triggers/fire`` is hit
by the deployment's external scheduler, which carries no Padhanam
Principal — so the path bypasses the bearer-auth middleware (it is in
the middleware's public-path set) and authenticates instead via the
``X-Internal-Secret`` header validated against
``MessagingSettings.internal_secret``.

Per S54 pre-write reconciliation: the brief's path
``apps/api/middleware/internal_secret.py`` conflicts with the existing
``apps/api/middleware.py`` module file (a directory and a module of the
same name cannot coexist). The internal-secret machinery lands here at
``apps/api/_internal_secret.py`` per the leading-underscore convention
established by ``_auth_errors.py`` and ``_messaging_errors.py``.

Fail-closed: a missing header, an empty configured secret, or a
mismatch all raise ``InternalSecretError`` (401). An empty configured
secret therefore rejects every request rather than accepting
unauthenticated fires — the deployment must configure the secret to
enable the endpoint. The comparison uses ``hmac.compare_digest`` to
avoid leaking secret length or content via timing.
"""

from __future__ import annotations

import hmac

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from apps.api._errors import ErrorResponse
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
    SecurityEventLogger,
)

_INTERNAL_SECRET_HEADER = "X-Internal-Secret"


class InternalSecretError(Exception):
    """Raised when the X-Internal-Secret header is missing or invalid.

    The handler translates to 401 ``internal_secret_invalid`` and fires
    an ``AUTH_FAILURE`` security event — the trigger endpoint bypasses
    bearer auth, so a failed internal-secret check is an authentication
    failure on that ingress.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"internal-secret authentication failed: {reason}")
        self.reason = reason


def verify_internal_secret(*, presented: str | None, configured: str) -> None:
    """Validate the presented secret against the configured one (fail-closed).

    Raises ``InternalSecretError`` when the presented header is missing,
    the configured secret is empty (endpoint disabled), or the two do
    not match under a constant-time comparison.
    """
    if not configured:
        raise InternalSecretError("endpoint disabled (no internal_secret configured)")
    if not presented:
        raise InternalSecretError("missing X-Internal-Secret header")
    if not hmac.compare_digest(presented, configured):
        raise InternalSecretError("internal secret mismatch")


async def _handle_internal_secret_error(
    request: Request, exc: InternalSecretError
) -> JSONResponse:
    logger: SecurityEventLogger | None = getattr(
        request.app.state, "security_events", None
    )
    if logger is not None:
        logger.emit(
            SecurityEvent(
                category=SecurityEventCategory.AUTH_FAILURE,
                principal_ref=None,
                tenant_id=None,
                action=f"{request.method} {request.url.path}",
                resource_ref=None,
                outcome="denied",
                metadata={"reason": f"internal_secret: {exc.reason}"},
            )
        )
    body = ErrorResponse(
        error_code="internal_secret_invalid",
        message=str(exc),
        correlation_id=getattr(request.state, "correlation_id", ""),
    )
    return JSONResponse(status_code=401, content=body.model_dump())


def register_internal_secret_error_handlers(app: FastAPI) -> None:
    """Register the internal-secret error handler on the FastAPI app (D145)."""
    app.add_exception_handler(
        InternalSecretError,  # type: ignore[arg-type]
        _handle_internal_secret_error,
    )


__all__ = [
    "InternalSecretError",
    "register_internal_secret_error_handlers",
    "verify_internal_secret",
    "_INTERNAL_SECRET_HEADER",
]
