"""Authentication coverage integration test.

Architectural commitment from D23: no FastAPI route ships without
authentication middleware in front of it. The middleware lives at the
ASGI layer (added via app.add_middleware) so it sits ahead of the
router and runs before any handler — including 404 fallbacks and
422 validation responses.

This test enumerates every route registered with the FastAPI app
(discovered from app.routes, not hardcoded) and asserts each one
returns 401 without a valid bearer token. /health is the only
exception, exempted explicitly in middleware._PUBLIC_PATHS. The
discovery from the live app object means adding a route without
auth coverage fails this test mechanically — the rule is enforced
by tooling, not by review.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.routing import APIRoute

from apps.api.middleware import _PUBLIC_PATHS


def _enumerate_routes(app: Any) -> list[tuple[str, str]]:
    """Return (method, path) pairs for every API route in the app."""
    pairs: list[tuple[str, str]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or {"GET"}:
            pairs.append((method, route.path))
    return pairs


def test_at_least_one_protected_route_is_registered(app: Any) -> None:
    """Sanity check — if the app has zero routes the rest of the test
    is vacuous, so guard against regressions that empty the router."""
    routes = _enumerate_routes(app)
    protected = [
        (method, path) for method, path in routes if path not in _PUBLIC_PATHS
    ]
    assert protected, (
        "no protected routes registered — auth-coverage assertion is vacuous"
    )


def test_every_route_requires_authentication(client: Any, app: Any) -> None:
    """Every non-public route returns 401 when no bearer is supplied."""
    routes = _enumerate_routes(app)
    failures: list[tuple[str, str, int]] = []
    for method, path in routes:
        if path in _PUBLIC_PATHS:
            continue
        response = client.request(method, path)
        if response.status_code != 401:
            failures.append((method, path, response.status_code))
    assert failures == [], (
        "routes reachable without authentication (D23 violation): "
        + repr(failures)
    )


def test_unmatched_path_returns_401_not_404(client: Any) -> None:
    """The middleware sits ahead of routing — a request to an unknown
    path with no bearer must return 401, not 404. This proves the
    middleware-on-every-route guarantee extends to the implicit fallback
    handler too.
    """
    response = client.get("/this-path-does-not-exist")
    assert response.status_code == 401


def test_health_route_is_public(client: Any) -> None:
    """/health is the operator probe Caddy uses; it bypasses auth."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_authenticated_request_passes(
    client: Any, dev_token: str
) -> None:
    """A valid dev-signed token reaches the router."""
    response = client.post(
        "/inference/completions",
        headers={"Authorization": f"Bearer {dev_token}"},
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "stub completion"
    assert body["total_tokens"] == 6


def test_invalid_credential_logs_security_event(
    client: Any, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed authentication emits a security event in the
    AUTH_FAILURE category (D26). The integration test wires the
    file-backed logger to a tmp path and asserts the JSONL line
    appears with the expected category.
    """
    # Re-import the module after patching so the next request creates
    # a fresh logger pointed at tmp_path.
    log_path = tmp_path / "security.jsonl"

    from padhanam.observability.security_events import (
        _FileSecurityEventLogger,
    )
    from apps.api import middleware as middleware_module

    monkeypatch.setattr(
        middleware_module,
        "file_security_event_logger",
        lambda: _FileSecurityEventLogger(path=log_path),
    )

    # Re-build the app with the monkeypatched logger factory.
    from apps.api.main import AppCompositions, create_app
    from contexts.inference.domain.completion import (
        Completion,
        Message,
        TokenUsage,
    )
    from padhanam.events import SynchronousEventBus

    class _Stub:
        def complete(self, messages, model, tenant_id) -> Completion:
            return Completion(
                text="x",
                model="m",
                usage=TokenUsage(input_tokens=1, output_tokens=1),
            )

    fresh_app = create_app(
        compositions=AppCompositions(
            inference_port=_Stub(),
            event_bus=SynchronousEventBus(),
        ),
        configure_tracing=False,
    )
    from fastapi.testclient import TestClient

    fresh_client = TestClient(fresh_app)

    response = fresh_client.post(
        "/inference/completions",
        headers={"Authorization": "Bearer not-a-real-token"},
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 401
    assert log_path.exists()
    contents = log_path.read_text(encoding="utf-8")
    assert '"category": "auth_failure"' in contents
    assert '"outcome": "denied"' in contents
