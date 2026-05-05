"""Shared fixtures for FastAPI integration tests."""

from __future__ import annotations

from typing import Any, Sequence

import pytest

from contexts.inference.domain.completion import (
    Completion,
    Message,
    TokenUsage,
)
from shared_kernel import TenantContext


# Deterministic fixture tenant_id for FastAPI integration tests. The
# value is UUID-shaped so the dev-token issuer's UUID validation
# accepts it; tests do not exercise the registry path because the
# get_tenant_context dependency is overridden in the app fixture.
_FIXTURE_TENANT_ID = "00000000-0000-4000-8000-0000000000a0"


class _StubInferencePort:
    """Substitute for the LiteLLM adapter in tests.

    Returns a fixed Completion regardless of input; tests assert on
    request shape, auth coverage, and trace propagation rather than
    inference quality.
    """

    def __init__(self) -> None:
        self.calls: list[
            tuple[Sequence[Message], str | None, TenantContext]
        ] = []

    def complete(
        self,
        messages: Sequence[Message],
        model: str | None,
        tenant_context: TenantContext,
    ) -> Completion:
        self.calls.append((messages, model, tenant_context))
        return Completion(
            text="stub completion",
            model=model or "stub-model",
            usage=TokenUsage(input_tokens=4, output_tokens=2),
            finish_reason="stop",
        )


@pytest.fixture
def stub_port() -> _StubInferencePort:
    return _StubInferencePort()


@pytest.fixture
def app(stub_port: _StubInferencePort, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Build the FastAPI app with the stub port and tracing disabled.

    Overrides ``get_tenant_context`` so tests do not need a wired
    registry. monkeypatches LITELLM_MASTER_KEY so InferenceSettings
    instantiation in adapter wiring (if any) does not need a real .env.
    """
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-integration")

    from apps.api.main import AppCompositions, create_app
    from apps.api.routers.inference import get_tenant_context
    from padhanam.events import SynchronousEventBus

    app = create_app(
        compositions=AppCompositions(
            inference_port=stub_port,
            event_bus=SynchronousEventBus(),
        ),
        configure_tracing=False,
    )
    app.dependency_overrides[get_tenant_context] = lambda: TenantContext(
        tenant_id=_FIXTURE_TENANT_ID,
        jurisdiction="eu-west",
        cost_attribution_id=_FIXTURE_TENANT_ID,
    )
    return app


@pytest.fixture
def client(app: Any) -> Any:
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture
def dev_token() -> str:
    """Issue a dev signed token for the fixture tenant / role inference.invoke."""
    from padhanam.security.auth import issue_dev_token

    return issue_dev_token(
        subject="alice",
        tenant_id=_FIXTURE_TENANT_ID,
        roles=["inference.invoke"],
    )
