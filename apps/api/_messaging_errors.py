"""Messaging HTTP error machinery (D129, S45).

A dedicated error module rather than an extension of
``apps/api/_errors.py``: that file is at 828 lines (the S44a
file-topology-budget finding), so the messaging error classes and
handlers land here per the redirect-away-from-over-budget-files
discipline — the same separate-module shape ``_auth_errors.py``
established at D104.

The composition root invokes ``register_messaging_error_handlers``
alongside the existing per-router registration functions. Error
codes (``message_not_found``, ``malformed_messaging_cursor``,
``invalid_messaging_filter``, ``webhook_signature_invalid``) join
the existing not-found / malformed-cursor / invalid-filter families
per D98.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from apps.api._errors import ErrorResponse
from apps.api.routers._messaging_query import InvalidMessagingFilterError
from contexts.messaging.domain.query_filters import MalformedCursorError
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
    SecurityEventLogger,
)


class MessageNotFoundError(Exception):
    """Raised by the messaging route when get_message returns None (D129).

    The HTTP handler translates to 404 ``message_not_found``.
    """

    def __init__(self, message_id: str) -> None:
        super().__init__(f"message {message_id} not found")
        self.message_id = message_id


class WebhookSignatureError(Exception):
    """Raised by the inbound webhook receiver when X-Twilio-Signature fails.

    The handler translates to 403 ``webhook_signature_invalid`` and
    fires an ``AUTH_FAILURE`` security event — an inbound webhook that
    fails signature verification is an authentication failure on the
    unauthenticated webhook ingress.
    """

    def __init__(self) -> None:
        super().__init__("X-Twilio-Signature verification failed")


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "")


async def _handle_message_not_found(
    request: Request, exc: MessageNotFoundError
) -> JSONResponse:
    body = ErrorResponse(
        error_code="message_not_found",
        message=str(exc),
        correlation_id=_correlation_id(request),
    )
    return JSONResponse(status_code=404, content=body.model_dump())


async def _handle_malformed_messaging_cursor(
    request: Request, exc: MalformedCursorError
) -> JSONResponse:
    body = ErrorResponse(
        error_code="malformed_messaging_cursor",
        message=str(exc),
        correlation_id=_correlation_id(request),
    )
    return JSONResponse(status_code=400, content=body.model_dump())


async def _handle_invalid_messaging_filter(
    request: Request, exc: InvalidMessagingFilterError
) -> JSONResponse:
    body = ErrorResponse(
        error_code="invalid_messaging_filter",
        message=str(exc),
        correlation_id=_correlation_id(request),
    )
    return JSONResponse(status_code=400, content=body.model_dump())


async def _handle_webhook_signature(
    request: Request, exc: WebhookSignatureError
) -> JSONResponse:
    """Translate ``WebhookSignatureError`` to 403 plus an AUTH_FAILURE event.

    The inbound webhook bypasses bearer auth (it carries no Padhanam
    Principal); its authentication is the X-Twilio-Signature. A failed
    verification is therefore an authentication failure on that
    ingress and is logged in the AUTH_FAILURE security-event stream.
    """
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
                metadata={"reason": "twilio_signature_verification_failed"},
            )
        )
    body = ErrorResponse(
        error_code="webhook_signature_invalid",
        message=str(exc),
        correlation_id=_correlation_id(request),
    )
    return JSONResponse(status_code=403, content=body.model_dump())


def register_messaging_error_handlers(app: FastAPI) -> None:
    """Register the messaging HTTP error handlers on the FastAPI app (D129)."""
    app.add_exception_handler(
        MessageNotFoundError, _handle_message_not_found  # type: ignore[arg-type]
    )
    app.add_exception_handler(
        MalformedCursorError,  # type: ignore[arg-type]
        _handle_malformed_messaging_cursor,
    )
    app.add_exception_handler(
        InvalidMessagingFilterError,  # type: ignore[arg-type]
        _handle_invalid_messaging_filter,
    )
    app.add_exception_handler(
        WebhookSignatureError, _handle_webhook_signature  # type: ignore[arg-type]
    )


__all__ = [
    "MessageNotFoundError",
    "WebhookSignatureError",
    "register_messaging_error_handlers",
]
