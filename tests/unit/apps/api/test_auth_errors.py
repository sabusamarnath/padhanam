"""Unit tests for the authentication-cross-cutting error machinery (D104, S38).

The handler functions are async coroutines that build JSONResponse
objects from Request + exception. We exercise them by constructing
minimal mock Request objects and asserting on the returned JSON body
shape.

The auth error machinery relocated from ``apps.api._errors`` to
``apps.api._auth_errors`` at S38 per D104. These tests moved from
``test_errors.py`` alongside the production code so the test surface
mirrors the module boundary.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from apps.api._auth_errors import (
    PrincipalTypeMismatchError,
    _handle_principal_type_mismatch,
    register_auth_error_handlers,
)
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
)


def _mock_request(correlation_id: str = "test-correlation-id") -> MagicMock:
    """Build a minimal mock Request with state.correlation_id."""
    request = MagicMock()
    request.state.correlation_id = correlation_id
    request.method = "GET"
    request.url.path = "/audit/events"
    request.app.state.security_events = None
    return request


class _CaptureLogger:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def emit(self, event: SecurityEvent) -> None:
        self.events.append(event)


# --------------------------------------------------------------------
# PrincipalTypeMismatchError handler shape.
# --------------------------------------------------------------------


def test_principal_type_mismatch_handler_returns_403_and_emits_authz_denial() -> None:
    request = _mock_request()
    logger = _CaptureLogger()
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
    logger = _CaptureLogger()
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
# register_auth_error_handlers.
# --------------------------------------------------------------------


def test_register_auth_error_handlers_registers_principal_type_mismatch_handler() -> None:
    """D104: register_auth_error_handlers wires PrincipalTypeMismatchError
    onto the FastAPI app's exception_handlers dict so the 403 path fires
    whenever a route dependency raises the typed error."""
    from fastapi import FastAPI

    app = FastAPI()
    register_auth_error_handlers(app)

    assert PrincipalTypeMismatchError in app.exception_handlers
    assert (
        app.exception_handlers[PrincipalTypeMismatchError]
        is _handle_principal_type_mismatch
    )


def test_register_audit_error_handlers_no_longer_registers_principal_type_mismatch() -> None:
    """D104: the audit registration function retains audit-specific
    handlers only; PrincipalTypeMismatchError moved out at S38."""
    from fastapi import FastAPI

    from apps.api._errors import register_audit_error_handlers

    app = FastAPI()
    register_audit_error_handlers(app)

    assert PrincipalTypeMismatchError not in app.exception_handlers
