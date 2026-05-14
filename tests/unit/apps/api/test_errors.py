"""Unit tests for the error response shape and handler functions (S34, D98).

The handler functions are async coroutines that build JSONResponse
objects from Request + exception. We exercise them by constructing
minimal mock Request objects and asserting on the returned JSON body
shape.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from apps.api._errors import (
    AuditEventNotFoundError,
    BoundTenantIdMismatchError,
    ErrorResponse,
    PrincipalTypeMismatchError,
    RunNotFoundError,
    _handle_audit_event_not_found,
    _handle_audit_query_routing_error,
    _handle_bound_tenant_mismatch,
    _handle_invalid_audit_filter,
    _handle_invalid_filter_range,
    _handle_malformed_audit_cursor,
    _handle_malformed_cursor,
    _handle_principal_type_mismatch,
    _handle_request_validation,
    _handle_run_not_found,
)
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
)


def _mock_request(correlation_id: str = "test-correlation-id") -> MagicMock:
    """Build a minimal mock Request with state.correlation_id."""
    request = MagicMock()
    request.state.correlation_id = correlation_id
    request.method = "GET"
    request.url.path = "/runs/test"
    request.app.state.security_events = None
    return request


# --------------------------------------------------------------------
# ErrorResponse shape.
# --------------------------------------------------------------------


def test_error_response_full_shape() -> None:
    response = ErrorResponse(
        error_code="malformed_cursor",
        message="something",
        correlation_id="abc",
        details={"k": "v"},
    )
    dumped = response.model_dump()
    assert dumped == {
        "error_code": "malformed_cursor",
        "message": "something",
        "correlation_id": "abc",
        "details": {"k": "v"},
    }


def test_error_response_details_optional() -> None:
    response = ErrorResponse(
        error_code="x", message="y", correlation_id="z"
    )
    assert response.details is None


# --------------------------------------------------------------------
# Malformed cursor handler.
# --------------------------------------------------------------------


def test_malformed_cursor_handler_returns_400() -> None:
    request = _mock_request()
    exc = MalformedCursorError("base64 decode failed: invalid")
    response = asyncio.run(_handle_malformed_cursor(request, exc))
    assert response.status_code == 400
    body = json.loads(response.body)
    assert body["error_code"] == "malformed_cursor"
    assert body["correlation_id"] == "test-correlation-id"
    assert "base64 decode failed" in body["message"]


# --------------------------------------------------------------------
# Invalid filter range handler.
# --------------------------------------------------------------------


def test_invalid_filter_range_handler_returns_400() -> None:
    request = _mock_request()
    exc = InvalidFilterRangeError("lower must be strictly earlier than upper")
    response = asyncio.run(_handle_invalid_filter_range(request, exc))
    assert response.status_code == 400
    body = json.loads(response.body)
    assert body["error_code"] == "invalid_filter_range"
    assert body["correlation_id"] == "test-correlation-id"


# --------------------------------------------------------------------
# Run not found handler.
# --------------------------------------------------------------------


def test_run_not_found_handler_returns_404() -> None:
    request = _mock_request()
    exc = RunNotFoundError("550e8400-e29b-41d4-a716-446655440000")
    response = asyncio.run(_handle_run_not_found(request, exc))
    assert response.status_code == 404
    body = json.loads(response.body)
    assert body["error_code"] == "run_not_found"
    assert "550e8400" in body["message"]


# --------------------------------------------------------------------
# Bound tenant mismatch handler.
# --------------------------------------------------------------------


class _CaptureLogger:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def emit(self, event: SecurityEvent) -> None:
        self.events.append(event)


def test_bound_tenant_mismatch_handler_returns_500_and_emits_security_event() -> None:
    request = _mock_request()
    logger = _CaptureLogger()
    request.app.state.security_events = logger
    request.state.principal = SimpleNamespace(
        subject="alice", tenant_id="00000000-0000-4000-8000-0000000000a1"
    )

    exc = BoundTenantIdMismatchError(ValueError("tenant mismatch"))
    response = asyncio.run(_handle_bound_tenant_mismatch(request, exc))

    assert response.status_code == 500
    body = json.loads(response.body)
    assert body["error_code"] == "internal_error"
    assert body["correlation_id"] == "test-correlation-id"
    assert body["message"] == "internal server error"
    assert len(logger.events) == 1
    event = logger.events[0]
    assert event.category == SecurityEventCategory.TENANT_SCOPE_VIOLATION
    assert event.principal_ref == "alice"
    assert event.outcome == "defence_in_depth_fired"
    assert event.metadata["severity"] == "critical"


def test_bound_tenant_mismatch_handler_without_logger_still_returns_500() -> None:
    """Defensive: handler still returns 500 even without a logger configured."""
    request = _mock_request()
    request.app.state.security_events = None
    exc = BoundTenantIdMismatchError(ValueError("tenant mismatch"))
    response = asyncio.run(_handle_bound_tenant_mismatch(request, exc))
    assert response.status_code == 500


# --------------------------------------------------------------------
# D103 (S37) audit-side handlers: principal_type_mismatch.
# --------------------------------------------------------------------


class _CaptureLoggerAudit:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def emit(self, event: SecurityEvent) -> None:
        self.events.append(event)


def test_principal_type_mismatch_handler_returns_403_and_emits_authz_denial() -> None:
    request = _mock_request()
    logger = _CaptureLoggerAudit()
    request.app.state.security_events = logger
    request.state.principal = SimpleNamespace(
        subject="ops-1", tenant_id=""
    )
    request.method = "GET"
    request.url.path = "/audit/events"

    exc = PrincipalTypeMismatchError(required="tenant", actual="platform_operator")
    response = asyncio.run(_handle_principal_type_mismatch(request, exc))

    assert response.status_code == 403
    body = json.loads(response.body)
    assert body["error_code"] == "principal_type_mismatch"
    assert body["correlation_id"] == "test-correlation-id"
    assert "tenant" in body["message"]
    assert "platform_operator" in body["message"]

    assert len(logger.events) == 1
    event = logger.events[0]
    assert event.category == SecurityEventCategory.AUTHZ_DENIAL
    assert event.principal_ref == "ops-1"
    assert event.outcome == "principal_type_mismatch"
    assert event.metadata["required_principal_type"] == "tenant"
    assert event.metadata["actual_principal_type"] == "platform_operator"
    assert event.action == "GET /audit/events"


def test_principal_type_mismatch_handler_without_logger_still_returns_403() -> None:
    request = _mock_request()
    request.app.state.security_events = None
    exc = PrincipalTypeMismatchError(
        required="platform_operator", actual="tenant"
    )
    response = asyncio.run(_handle_principal_type_mismatch(request, exc))
    assert response.status_code == 403


def test_principal_type_mismatch_handler_captures_tenant_id_for_tenant_principal() -> None:
    """When a tenant token hits a platform-operator route, the security
    event metadata captures the tenant_id for forensic traceability."""
    request = _mock_request()
    logger = _CaptureLoggerAudit()
    request.app.state.security_events = logger
    request.state.principal = SimpleNamespace(
        subject="alice", tenant_id="00000000-0000-4000-8000-0000000000a1"
    )

    exc = PrincipalTypeMismatchError(
        required="platform_operator", actual="tenant"
    )
    asyncio.run(_handle_principal_type_mismatch(request, exc))

    assert logger.events[0].tenant_id == "00000000-0000-4000-8000-0000000000a1"


# --------------------------------------------------------------------
# D103 (S37) audit-side handlers: audit_event_not_found.
# --------------------------------------------------------------------


def test_audit_event_not_found_handler_returns_404() -> None:
    request = _mock_request()
    exc = AuditEventNotFoundError("550e8400-e29b-41d4-a716-446655440000")
    response = asyncio.run(_handle_audit_event_not_found(request, exc))
    assert response.status_code == 404
    body = json.loads(response.body)
    assert body["error_code"] == "audit_event_not_found"
    assert "550e8400" in body["message"]


# --------------------------------------------------------------------
# D103 (S37) audit-side handlers: invalid_audit_filter.
# --------------------------------------------------------------------


def test_invalid_audit_filter_handler_returns_400() -> None:
    request = _mock_request()
    exc = InvalidAuditFilterError(
        "resource_id filter requires resource_type"
    )
    response = asyncio.run(_handle_invalid_audit_filter(request, exc))
    assert response.status_code == 400
    body = json.loads(response.body)
    assert body["error_code"] == "invalid_audit_filter"
    assert "resource_id" in body["message"]


# --------------------------------------------------------------------
# D103 (S37) audit-side handlers: malformed_audit_cursor.
# --------------------------------------------------------------------


def test_malformed_audit_cursor_handler_returns_400() -> None:
    request = _mock_request()
    exc = AuditMalformedCursorError("base64 decode failed: invalid")
    response = asyncio.run(_handle_malformed_audit_cursor(request, exc))
    assert response.status_code == 400
    body = json.loads(response.body)
    assert body["error_code"] == "malformed_audit_cursor"
    assert "base64 decode failed" in body["message"]


# --------------------------------------------------------------------
# D103 (S37) audit-side handlers: invalid_audit_routing.
# --------------------------------------------------------------------


def test_audit_query_routing_handler_returns_400() -> None:
    request = _mock_request()
    exc = AuditQueryRoutingError(
        "destination 'per_tenant' requires a tenant_context"
    )
    response = asyncio.run(_handle_audit_query_routing_error(request, exc))
    assert response.status_code == 400
    body = json.loads(response.body)
    assert body["error_code"] == "invalid_audit_routing"
    assert "per_tenant" in body["message"]


# --------------------------------------------------------------------
# Request validation handler.
# --------------------------------------------------------------------


def test_request_validation_handler_returns_422_with_errors() -> None:
    from fastapi.exceptions import RequestValidationError

    # Build a RequestValidationError with one synthetic error.
    errors = [
        {
            "type": "value_error",
            "loc": ("query", "page_size"),
            "msg": "field required",
            "input": None,
        }
    ]
    exc = RequestValidationError(errors=errors)
    request = _mock_request()
    response = asyncio.run(_handle_request_validation(request, exc))
    assert response.status_code == 422
    body = json.loads(response.body)
    assert body["error_code"] == "validation_error"
    assert body["correlation_id"] == "test-correlation-id"
    assert body["details"]["errors"]
