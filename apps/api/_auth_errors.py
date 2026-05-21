"""Authentication-cross-cutting error machinery (D104, S38).

This module owns the error types raised by shared authentication
dependencies — types that are not specific to any one bounded
context's router and that any new router consuming the shared
``get_tenant_context`` or ``get_platform_operator_principal``
chokepoints can raise.

Before S38 the auth-cross-cutting machinery lived inside
``apps/api/_errors.py`` alongside the run-history and audit
error handlers; the S37 close placed
``PrincipalTypeMismatchError`` and its handler there per
finding-4 resolution. The S38 relocation (D104, alternative (a)
trigger fired at the second router using the shared chokepoint)
extracts the auth-cross-cutting surface into this module so each
new router does not need to copy or import audit-specific
registration to gain the 403-plus-AUTHZ_DENIAL handler.

The composition root at ``apps/api/main.py`` invokes
``register_auth_error_handlers`` alongside the existing
per-router registration functions. Audit's
``register_audit_error_handlers`` retains audit-specific error
classes only.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from apps.api._errors import ErrorResponse
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
    SecurityEventLogger,
)
from shared_kernel import TenantId
from shared_kernel.authorisation import AuthorisationDenied


class PrincipalTypeMismatchError(Exception):
    """Raised when the route's required principal type does not match the
    authenticated principal's type (D103, S37 commit 4; relocated at D104, S38).

    Three call sites at S37 and S38:

    - ``apps.api.middleware.get_platform_operator_principal`` raises
      when a tenant-typed token hits a ``/platform/audit/*`` route.
    - ``apps.api.routers.inference.get_tenant_context`` raises when a
      platform-operator-typed token hits any tenant-scoped route
      (run-history, audit-per-tenant, ingestion at S38).
    - Future route dependencies that gate on principal type follow the
      same pattern.

    Carries the required and actual principal-type values so the
    error handler can surface a typed 403 with informative metadata
    AND fire an ``AUTHZ_DENIAL`` security event identifying the
    attempted-route plus the offending token's principal_type.
    """

    def __init__(
        self,
        *,
        required: str,
        actual: str,
    ) -> None:
        super().__init__(
            f"authenticated principal lacks the required type {required!r} "
            f"for this route; got {actual!r}"
        )
        self.required = required
        self.actual = actual


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "")


async def _handle_principal_type_mismatch(
    request: Request, exc: PrincipalTypeMismatchError
) -> JSONResponse:
    """Translate ``PrincipalTypeMismatchError`` to 403 + AUTHZ_DENIAL event (D103).

    Fires an ``AUTHZ_DENIAL`` security event carrying the attempted
    route, the offending token's actual principal_type, the
    correlation_id (if present on request.state.principal), and the
    request timestamp. The handler is the single place the 403 path
    is emitted, so the security event guard is centralised.
    """
    logger: SecurityEventLogger | None = getattr(
        request.app.state, "security_events", None
    )
    if logger is not None:
        principal = getattr(request.state, "principal", None)
        principal_ref = principal.subject if principal is not None else None
        # Tenant_id captured for forensic traceability when the
        # offending token is tenant-typed; for platform-operator
        # tokens (which carry the empty sentinel), the metadata
        # surfaces "no tenant" via the actual=platform_operator
        # marker.
        tenant_id_for_event: TenantId | None = None
        if principal is not None and principal.tenant_id:
            tenant_id_for_event = TenantId(str(principal.tenant_id))
        logger.emit(
            SecurityEvent(
                category=SecurityEventCategory.AUTHZ_DENIAL,
                principal_ref=principal_ref,
                tenant_id=tenant_id_for_event,
                action=f"{request.method} {request.url.path}",
                resource_ref=None,
                outcome="principal_type_mismatch",
                metadata={
                    "required_principal_type": exc.required,
                    "actual_principal_type": exc.actual,
                },
            )
        )

    body = ErrorResponse(
        error_code="principal_type_mismatch",
        message=str(exc),
        correlation_id=_correlation_id(request),
    )
    return JSONResponse(status_code=403, content=body.model_dump())


async def _handle_authorisation_denied(
    request: Request, exc: AuthorisationDenied
) -> JSONResponse:
    """Translate ``AuthorisationDenied`` to 403 + AUTHZ_DENIAL event (D126).

    ``AuthorisationDenied`` is raised by the ``requires_authorisation``
    decorator at the use-case boundary (``shared_kernel/authorisation.py``)
    when an actor lacks a required permission. It is auth-cross-cutting
    — raised by the shared decorator, not by any one router — so its
    handler belongs in this module per the D104 auth-cross-cutting
    placement, alongside ``PrincipalTypeMismatchError``.

    The handler fires an ``AUTHZ_DENIAL`` security event carrying the
    attempted route, the required permission, and the offending
    actor_id, then returns a 403 ``ErrorResponse``. The response
    message names the required permission only — never the actor's
    full authorisation set.
    """
    logger: SecurityEventLogger | None = getattr(
        request.app.state, "security_events", None
    )
    if logger is not None:
        principal = getattr(request.state, "principal", None)
        principal_ref = principal.subject if principal is not None else None
        tenant_id_for_event: TenantId | None = None
        if principal is not None and principal.tenant_id:
            tenant_id_for_event = TenantId(str(principal.tenant_id))
        logger.emit(
            SecurityEvent(
                category=SecurityEventCategory.AUTHZ_DENIAL,
                principal_ref=principal_ref,
                tenant_id=tenant_id_for_event,
                action=f"{request.method} {request.url.path}",
                resource_ref=None,
                outcome="authorisation_denied",
                metadata={
                    "required_permission": exc.permission,
                    "actor_id": exc.actor_id,
                },
            )
        )

    body = ErrorResponse(
        error_code="authorisation_denied",
        message=(
            "the authenticated actor lacks the required authorisation "
            f"{exc.permission!r} for this operation"
        ),
        correlation_id=_correlation_id(request),
    )
    return JSONResponse(status_code=403, content=body.model_dump())


def register_auth_error_handlers(app: FastAPI) -> None:
    """Register the authentication-cross-cutting error handlers on the FastAPI app (D104, S38; D126, S44a).

    Called from create_app at composition time alongside the existing
    per-router registration functions (``register_run_history_error_handlers``,
    ``register_audit_error_handlers``). Each new router that consumes
    the shared authentication chokepoints inherits the 403 + AUTHZ_DENIAL
    path without copying registration code.

    Handlers registered:

    - ``PrincipalTypeMismatchError`` -> 403 ``principal_type_mismatch``
      with ``AUTHZ_DENIAL`` security event.
    - ``AuthorisationDenied`` -> 403 ``authorisation_denied`` with
      ``AUTHZ_DENIAL`` security event (D126; raised by the
      ``requires_authorisation`` use-case-boundary decorator).
    """
    app.add_exception_handler(
        PrincipalTypeMismatchError, _handle_principal_type_mismatch  # type: ignore[arg-type]
    )
    app.add_exception_handler(
        AuthorisationDenied, _handle_authorisation_denied  # type: ignore[arg-type]
    )


__all__ = [
    "PrincipalTypeMismatchError",
    "register_auth_error_handlers",
]
