"""Shared fixtures for FastAPI integration tests."""

from __future__ import annotations

from typing import Any, Sequence

import pytest

from contexts.inference.domain.completion import (
    Completion,
    Message,
    TokenUsage,
)
from shared_kernel import TenantId


class _StubInferencePort:
    """Substitute for the LiteLLM adapter in tests.

    Returns a fixed Completion regardless of input; tests assert on
    request shape, auth coverage, and trace propagation rather than
    inference quality.
    """

    def __init__(self) -> None:
        self.calls: list[
            tuple[Sequence[Message], str | None, TenantId]
        ] = []

    def complete(
        self,
        messages: Sequence[Message],
        model: str | None,
        tenant_id: TenantId,
    ) -> Completion:
        self.calls.append((messages, model, tenant_id))
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

    monkeypatches LITELLM_MASTER_KEY so InferenceSettings instantiation
    in adapter wiring (if any) does not need a real .env.
    """
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-integration")

    from apps.api.main import AppCompositions, create_app
    from vadakkan.events import SynchronousEventBus

    return create_app(
        compositions=AppCompositions(
            inference_port=stub_port,
            event_bus=SynchronousEventBus(),
        ),
        configure_tracing=False,
    )


@pytest.fixture
def client(app: Any) -> Any:
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture
def dev_token() -> str:
    """Issue a dev signed token for tenant-a / role audit.read."""
    from vadakkan.security.auth import issue_dev_token

    return issue_dev_token(
        subject="alice",
        tenant_id="tenant-a",
        roles=["inference.invoke"],
    )
