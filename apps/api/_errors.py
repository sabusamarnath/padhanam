"""Error response body shape and exception handlers (D98, S34).

ErrorResponse body shape per D98:

    {
      "error_code": "machine_readable_identifier",
      "message": "human-readable explanation",
      "correlation_id": "uuid4-per-request",
      "details": {...}  # optional field-level errors for validation
    }

The shape applies to run-history routes at S34. Existing routes
continue using FastAPI's default ``HTTPException`` shape
(``{"detail": "..."}``); future refresh moves them to the new shape
without churning the wire format unilaterally.

Custom exceptions raised by the run-history routes:

- ``RunNotFoundError`` — raised when ``reader.get_run`` returns None.
  Translates to 404 ``run_not_found`` with a
  ``TENANT_SCOPE_VIOLATION`` security event already emitted at the
  route handler.

- ``BoundTenantIdMismatchError`` — raised when the reader's
  defence-in-depth tenant-id check fires. Should never fire above the
  data layer in production; translates to 500 ``internal_error`` with
  a ``TENANT_SCOPE_VIOLATION`` security event fired at the handler
  because firing means a bug above the data layer.

Domain exceptions handled at the HTTP boundary:

- ``MalformedCursorError`` from
  ``contexts.run_history.domain.query_filters`` — 400
  ``malformed_cursor``.

- ``InvalidFilterRangeError`` from
  ``apps.api.routers._run_history_query`` — 400
  ``invalid_filter_range``.

- ``RequestValidationError`` from FastAPI — 422 ``validation_error``
  with field-level details preserved.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from apps.api.routers._audit_query import InvalidAuditFilterError
from apps.api.routers._run_history_query import InvalidFilterRangeError
from contexts.audit.domain.query_filters import (
    MalformedCursorError as AuditMalformedCursorError,
)
from contexts.audit.ports.reader import AuditQueryRoutingError
from contexts.run_history.domain.query_filters import MalformedCursorError
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
    SecurityEventLogger,
)
from shared_kernel import TenantId


class ErrorResponse(BaseModel):
    """The S34 error response body shape per D98."""

    error_code: str
    message: str
    correlation_id: str
    details: dict[str, Any] | None = None


class RunNotFoundError(Exception):
    """Raised by the run-history route when reader.get_run returns None.

    The HTTP handler translates to 404 ``run_not_found``. The route
    fires the ``TENANT_SCOPE_VIOLATION`` security event before
    raising; the handler is a pure shape translator.
    """

    def __init__(self, run_id: str) -> None:
        super().__init__(f"run {run_id} not found")
        self.run_id = run_id


class AuditEventNotFoundError(Exception):
    """Raised when the audit reader returns ``None`` for a single-event lookup.

    The HTTP handler translates to 404 ``audit_event_not_found``.
    No security event fires for this case — cross-tenant invisibility
    is structurally indistinguishable from genuine not-found at the
    list-view altitude, and at the single-event-lookup altitude the
    audit reader cannot leak existence on another tenant because the
    per-tenant destination scopes the query by tenant context.
    """

    def __init__(self, event_id: str) -> None:
        super().__init__(f"audit event {event_id} not found")
        self.event_id = event_id


class BoundTenantIdMismatchError(Exception):
    """Raised when the reader's bound-tenant-id defence-in-depth fires.

    This is a structural defence-in-depth path that should never fire
    in production (the route layer enforces tenant routing at the
    principal level; the reader's bound-id check is a second-layer
    assertion). Firing means a bug above the data layer; the handler
    translates to 500 ``internal_error`` and emits a synchronous
    ``TENANT_SCOPE_VIOLATION`` security event with severity-equivalent
    metadata because the operational urgency is high.
    """

    def __init__(self, original: Exception) -> None:
        super().__init__(str(original))
        self.original = original


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "")


async def _handle_malformed_cursor(
    request: Request, exc: MalformedCursorError
) -> JSONResponse:
    body = ErrorResponse(
        error_code="malformed_cursor",
        message=str(exc),
        correlation_id=_correlation_id(request),
    )
    return JSONResponse(status_code=400, content=body.model_dump())


async def _handle_invalid_filter_range(
    request: Request, exc: InvalidFilterRangeError
) -> JSONResponse:
    body = ErrorResponse(
        error_code="invalid_filter_range",
        message=str(exc),
        correlation_id=_correlation_id(request),
    )
    return JSONResponse(status_code=400, content=body.model_dump())


async def _handle_run_not_found(
    request: Request, exc: RunNotFoundError
) -> JSONResponse:
    body = ErrorResponse(
        error_code="run_not_found",
        message=str(exc),
        correlation_id=_correlation_id(request),
    )
    return JSONResponse(status_code=404, content=body.model_dump())


async def _handle_bound_tenant_mismatch(
    request: Request, exc: BoundTenantIdMismatchError
) -> JSONResponse:
    """Map the reader's defence-in-depth ValueError to 500 plus security event.

    Synchronous event firing per D98 alternative (h): tenant-scope
    violations are operationally urgent; BackgroundTasks would defer
    the alerting signal off the request path.
    """
    logger: SecurityEventLogger | None = getattr(
        request.app.state, "security_events", None
    )
    if logger is not None:
        principal = getattr(request.state, "principal", None)
        principal_ref = principal.subject if principal is not None else None
        tenant_id = (
            TenantId(str(principal.tenant_id)) if principal is not None else None
        )
        logger.emit(
            SecurityEvent(
                category=SecurityEventCategory.TENANT_SCOPE_VIOLATION,
                principal_ref=principal_ref,
                tenant_id=tenant_id,
                action=f"{request.method} {request.url.path}",
                resource_ref=None,
                outcome="defence_in_depth_fired",
                metadata={
                    "severity": "critical",
                    "reason": str(exc),
                    "note": (
                        "Reader's bound-tenant-id mismatch fired above the data "
                        "layer; this is a bug — the route-layer principal check "
                        "should have caught the mismatch first"
                    ),
                },
            )
        )

    body = ErrorResponse(
        error_code="internal_error",
        message="internal server error",
        correlation_id=_correlation_id(request),
    )
    return JSONResponse(status_code=500, content=body.model_dump())


async def _handle_audit_event_not_found(
    request: Request, exc: AuditEventNotFoundError
) -> JSONResponse:
    body = ErrorResponse(
        error_code="audit_event_not_found",
        message=str(exc),
        correlation_id=_correlation_id(request),
    )
    return JSONResponse(status_code=404, content=body.model_dump())


async def _handle_invalid_audit_filter(
    request: Request, exc: InvalidAuditFilterError
) -> JSONResponse:
    body = ErrorResponse(
        error_code="invalid_audit_filter",
        message=str(exc),
        correlation_id=_correlation_id(request),
    )
    return JSONResponse(status_code=400, content=body.model_dump())


async def _handle_malformed_audit_cursor(
    request: Request, exc: AuditMalformedCursorError
) -> JSONResponse:
    body = ErrorResponse(
        error_code="malformed_audit_cursor",
        message=str(exc),
        correlation_id=_correlation_id(request),
    )
    return JSONResponse(status_code=400, content=body.model_dump())


async def _handle_audit_query_routing_error(
    request: Request, exc: AuditQueryRoutingError
) -> JSONResponse:
    """Translate ``AuditQueryRoutingError`` to 400 ``invalid_audit_routing``.

    Defence-in-depth: the audit reader's port-surface invariant
    (destination + tenant_context agreement) should always be
    satisfied by the route layer's dependency injection, but if a
    bug above the data layer ever supplies a mismatched pair, the
    400 path surfaces cleanly rather than a 500.
    """
    body = ErrorResponse(
        error_code="invalid_audit_routing",
        message=str(exc),
        correlation_id=_correlation_id(request),
    )
    return JSONResponse(status_code=400, content=body.model_dump())


async def _handle_request_validation(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    body = ErrorResponse(
        error_code="validation_error",
        message="request validation failed",
        correlation_id=_correlation_id(request),
        details={"errors": exc.errors()},
    )
    return JSONResponse(status_code=422, content=body.model_dump())


def register_run_history_error_handlers(app: FastAPI) -> None:
    """Register the run-history error handlers on the FastAPI app.

    Called from create_app at composition time. The handlers are
    scoped to the exception classes the run-history routes raise plus
    the FastAPI RequestValidationError; existing routes' HTTPException
    handling continues using FastAPI's default 422 / 404 / 500 shapes
    until those routes refresh to the new ErrorResponse shape.
    """
    app.add_exception_handler(MalformedCursorError, _handle_malformed_cursor)  # type: ignore[arg-type]
    app.add_exception_handler(InvalidFilterRangeError, _handle_invalid_filter_range)  # type: ignore[arg-type]
    app.add_exception_handler(RunNotFoundError, _handle_run_not_found)  # type: ignore[arg-type]
    app.add_exception_handler(
        BoundTenantIdMismatchError, _handle_bound_tenant_mismatch  # type: ignore[arg-type]
    )
    app.add_exception_handler(RequestValidationError, _handle_request_validation)  # type: ignore[arg-type]


def register_audit_error_handlers(app: FastAPI) -> None:
    """Register the audit error handlers on the FastAPI app (D103, S37; refined D104, S38).

    Parallel to ``register_run_history_error_handlers`` per S37
    pre-write reconciliation finding 4 user-question resolution: each
    audit-context exception class registers its own handler in this
    function; the composition root at ``apps/api/main.py`` calls both
    ``register_run_history_error_handlers`` and
    ``register_audit_error_handlers`` at app construction time.

    The ``PrincipalTypeMismatchError`` handler moved out at S38 (D104)
    to a sibling ``register_auth_error_handlers`` at
    ``apps/api/_auth_errors.py``; the auth-cross-cutting surface is
    now owned by the auth module so ingestion (S38) and any future
    routers consuming the shared ``get_tenant_context`` chokepoint
    inherit the 403 + AUTHZ_DENIAL path without coupling to audit.

    Handlers registered here (audit-specific only):

    - ``AuditEventNotFoundError`` -> 404 ``audit_event_not_found``.
    - ``InvalidAuditFilterError`` -> 400 ``invalid_audit_filter``.
    - ``AuditMalformedCursorError`` -> 400 ``malformed_audit_cursor``.
    - ``AuditQueryRoutingError`` -> 400 ``invalid_audit_routing``
      (defence-in-depth path; should never fire in production).
    """
    app.add_exception_handler(
        AuditEventNotFoundError, _handle_audit_event_not_found  # type: ignore[arg-type]
    )
    app.add_exception_handler(
        InvalidAuditFilterError, _handle_invalid_audit_filter  # type: ignore[arg-type]
    )
    app.add_exception_handler(
        AuditMalformedCursorError, _handle_malformed_audit_cursor  # type: ignore[arg-type]
    )
    app.add_exception_handler(
        AuditQueryRoutingError, _handle_audit_query_routing_error  # type: ignore[arg-type]
    )


__all__ = [
    "AuditEventNotFoundError",
    "BoundTenantIdMismatchError",
    "ErrorResponse",
    "RunNotFoundError",
    "register_audit_error_handlers",
    "register_run_history_error_handlers",
]
