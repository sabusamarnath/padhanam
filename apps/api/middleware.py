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

import uuid
from typing import Annotated, Awaitable, Callable

from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from padhanam.observability import (
    SecurityEvent,
    SecurityEventCategory,
    SecurityEventLogger,
    file_security_event_logger,
)
from padhanam.security import (
    AuthError,
    PlatformOperatorPrincipal,
    Principal,
    PrincipalType,
    verify_credential,
)
from shared_kernel import ActorContext
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles


CORRELATION_ID_HEADER = "X-Correlation-Id"


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


def get_platform_operator_principal(
    request: Request,
) -> PlatformOperatorPrincipal:
    """FastAPI dependency: resolve the principal to a platform-operator marker (D103).

    Routes that declare ``Depends(get_platform_operator_principal)``
    are gated to platform-operator-typed principals. Tenant-typed
    tokens raise ``PrincipalTypeMismatchError``, which the registered
    handler at ``apps/api/_auth_errors.py`` (D104, S38) translates to
    HTTP 403 plus an ``AUTHZ_DENIAL`` security event.

    The middleware authenticates the credential and stores the
    ``Principal`` on ``request.state.principal`` regardless of
    principal type; this dependency narrows the surface to a
    ``PlatformOperatorPrincipal`` thin marker that downstream
    handlers consume without re-checking the discriminator.
    """
    # Imported lazily to preserve the original circular-import guard
    # shape: ``apps.api.routers`` modules import from middleware at
    # load time, and the auth-error module pulls in the shared
    # ``ErrorResponse`` from ``apps.api._errors``. Lazy import keeps
    # the dependency edge contained inside the function call.
    from apps.api._auth_errors import PrincipalTypeMismatchError

    principal: Principal = request.state.principal
    if principal.principal_type is not PrincipalType.PLATFORM_OPERATOR:
        raise PrincipalTypeMismatchError(
            required=PrincipalType.PLATFORM_OPERATOR.value,
            actual=principal.principal_type.value,
        )
    return PlatformOperatorPrincipal(
        subject=principal.subject,
        credential_ref=principal.credential_ref,
    )


async def get_actor_context(
    request: Request,
    principal: Annotated[Principal, Depends(get_principal)],
) -> ActorContext:
    """FastAPI dependency: resolve the request-scoped ActorContext (D126, S44a).

    Composes the registry-resolved TenantContext with the
    Principal-derived actor identity. ``get_tenant_context`` is
    imported lazily: ``apps.api.routers.inference`` imports
    ``get_principal`` from this module at load time, so a module-scope
    import of ``get_tenant_context`` here would close the cycle. The
    lazy import follows the same cycle-avoidance discipline
    ``get_tenant_context`` itself uses for ``_auth_errors``.

    Phase 2-A populates ``role_list`` with the single ``operator``
    role and resolves ``authorisation_set`` through the hardcoded
    policy at ``shared_kernel/authorisation.py``. Tenant-typed
    principals only: ``get_tenant_context`` raises
    ``PrincipalTypeMismatchError`` for platform-operator tokens, and
    the 503/400/404 registry-resolution paths are inherited unchanged.

    Routes that need only adapter-layer tenant context keep depending
    on ``get_tenant_context`` directly; routes that enforce
    use-case-boundary authorisation depend on this resolver.
    """
    from apps.api.routers.inference import get_tenant_context

    tenant_context = await get_tenant_context(request, principal)
    role_list = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=tenant_context,
        actor_id=principal.subject,
        role_list=role_list,
        authorisation_set=authorisations_for_roles(role_list),
    )


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Generate a per-request correlation ID for forensic correlation (S34, D98).

    Generates ``uuid4()`` on every inbound request, attaches it to
    ``request.state.correlation_id``, and returns the value in the
    ``X-Correlation-Id`` response header. Exception handlers and route
    handlers pull from request state to populate the
    ``ErrorResponse.correlation_id`` field per D98.

    The middleware runs unconditionally on every request including
    health probes and unmatched paths, so error responses always
    carry a correlation_id for forensic correlation.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response
