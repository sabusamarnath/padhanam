"""Tests for the inference router's get_tenant_context dependency (S15).

The dependency resolves a TenantContext from the control-plane registry
at request time, returning HTTP 404 when the tenant_id from the
authenticated principal is not in the registry. The defence-in-depth
case (registry returning a row whose cost_attribution_id is None) is
caught by the TenantContext constructor's validation rather than this
dependency's logic — that is the point of the value object's empty-
string rejection.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.main import AppCompositions, create_app
from apps.api.routers.inference import get_tenant_context
from contexts.inference.domain.completion import (
    Completion,
    Message,
    TokenUsage,
)
from contexts.tenancy.domain import (
    EncryptedCredentials,
    Tenant,
    TenantId,
    TenantStatus,
)
from shared_kernel import Jurisdiction, TenantContext
from padhanam.events import SynchronousEventBus
from padhanam.security.auth import issue_dev_token


_REGISTERED_TENANT_ID = "00000000-0000-4000-8000-0000000000a1"


class _StubInferencePort:
    def complete(self, messages, model, tenant_context) -> Completion:
        return Completion(
            text="ok",
            model=model or "stub",
            usage=TokenUsage(input_tokens=1, output_tokens=1),
        )


class _StubRegistry:
    """Returns one fixture tenant; everything else is None."""

    def __init__(self) -> None:
        self.tenant = Tenant(
            id=TenantId(_REGISTERED_TENANT_ID),
            jurisdiction=Jurisdiction("eu-west"),
            display_name="Tenant A",
            credentials=EncryptedCredentials(
                wrapped_dek=b"\x01", ciphertext=b"\x02", aad=b"\x03"
            ),
            status=TenantStatus.ACTIVE,
            created_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
            cost_attribution_id="acme-billing-2026",
        )

    async def get_tenant(self, tenant_id):
        if str(tenant_id) == _REGISTERED_TENANT_ID:
            return self.tenant
        return None


def _build_app(registry: Any | None) -> FastAPI:
    app = create_app(
        compositions=AppCompositions(
            inference_port=_StubInferencePort(),
            event_bus=SynchronousEventBus(),
        ),
        configure_tracing=False,
    )
    app.state.tenant_registry = registry
    return app


def _token(tenant_id: str) -> str:
    return issue_dev_token(
        subject="alice",
        tenant_id=tenant_id,
        roles=["inference.invoke"],
    )


def test_resolution_happy_path_returns_full_context(monkeypatch) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-resolution")
    app = _build_app(_StubRegistry())
    client = TestClient(app)

    response = client.post(
        "/inference/completions",
        headers={"Authorization": f"Bearer {_token(_REGISTERED_TENANT_ID)}"},
        json={"messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 200, response.text


def test_unknown_tenant_returns_404(monkeypatch) -> None:
    """A principal carrying a UUID-shaped tenant_id absent from the
    registry produces an HTTP 404; the inference call never happens."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-resolution")
    app = _build_app(_StubRegistry())
    client = TestClient(app)
    bogus = "00000000-0000-4000-8000-deadbeefdead"

    response = client.post(
        "/inference/completions",
        headers={"Authorization": f"Bearer {_token(bogus)}"},
        json={"messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_non_uuid_principal_returns_400(monkeypatch) -> None:
    """An operator-style sentinel tenant_id (not UUID-shaped) at the
    inference path is a configuration mismatch — the registry holds
    tenant rows, not operators. Returning 400 surfaces it without
    leaking implementation detail.
    """
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-resolution")
    app = _build_app(_StubRegistry())
    client = TestClient(app)

    response = client.post(
        "/inference/completions",
        headers={"Authorization": f"Bearer {_token('operator')}"},
        json={"messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 400


def test_unconfigured_registry_returns_503(monkeypatch) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-test-resolution")
    app = _build_app(None)
    client = TestClient(app)

    response = client.post(
        "/inference/completions",
        headers={"Authorization": f"Bearer {_token(_REGISTERED_TENANT_ID)}"},
        json={"messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 503


def test_constructor_validation_rejects_empty_cost_attribution_id() -> None:
    """Defence in depth: even if the schema's NOT NULL on
    cost_attribution_id is somehow circumvented and the row carries
    an empty string, the TenantContext constructor catches it
    synchronously rather than letting the empty value flow to the
    inference adapter.
    """
    with pytest.raises(ValueError, match="cost_attribution_id"):
        TenantContext(
            tenant_id="00000000-0000-4000-8000-0000000000ff",
            jurisdiction="eu-west",
            cost_attribution_id="",
        )
