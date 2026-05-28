"""Integration tests for the HTTP trigger endpoint (D145, D147, S54).

Builds a minimal FastAPI app with the trigger router plus a
MessagingComposition whose broadcast registry holds a stub
BroadcastFlow implementer for DAILY_SCHEDULED. Exercises:

- internal-secret authentication (missing / wrong / valid header);
- the fresh-fire path (200 ACCEPTED; fired_triggers inserted;
  BROADCAST_INITIATED audited; implementer fired);
- the duplicate path (200 ALREADY_FIRED; no second audit; no second
  fire).

The composition uses the in-memory FakeFiredTriggersRepository and a
synchronous broadcast dispatch wrapper so the stub implementer fires
inline (the production InProcessBroadcastDispatchAdapter spawns a
background task; the test wrapper awaits it for deterministic
assertions).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api._internal_secret import register_internal_secret_error_handlers
from apps.api._messaging_wiring import MessagingComposition
from apps.api.routers import triggers as triggers_router
from contexts.messaging.adapters.channel_resolver.static_config_channel_resolver_adapter import (  # noqa: E501
    StaticConfigChannelResolverAdapter,
)
from contexts.messaging.domain.channel_type import ChannelType
from shared_kernel.broadcast_flow import (
    BroadcastResponse,
    BroadcastTriggerType,
    TriggerContext,
)
from shared_kernel.conversation_flow import ArtefactCitation
from tests.unit.contexts.messaging.application._fakes import (
    FakeAuditPort,
    FakeFiredTriggersRepository,
    FakeMessageDeliveryPort,
    FakeMessageRepository,
)

_TENANT_ID = "00000000-0000-4000-8000-00000000a001"
_SECRET = "test-internal-secret-1234"
_FIRE_PATH = "/api/v1/internal/triggers/fire"


@dataclass(frozen=True)
class _StubBroadcastResponse:
    cited_intake_records: tuple[UUID, ...]
    cited_audit_events: tuple[UUID, ...]
    cited_artefacts: tuple[ArtefactCitation, ...]


@dataclass
class _StubImplementer:
    fired: list[TriggerContext] = field(default_factory=list)

    async def fire(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        trigger_context: TriggerContext,
    ) -> BroadcastResponse:
        self.fired.append(trigger_context)
        return _StubBroadcastResponse(
            cited_intake_records=(),
            cited_audit_events=(),
            cited_artefacts=(),
        )


@dataclass
class _SyncBroadcastDispatch:
    """Dispatch wrapper that fires the registered implementer inline."""

    implementer: _StubImplementer

    async def dispatch(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        trigger_context: TriggerContext,
        context: dict[str, Any] | None = None,
    ) -> None:
        await self.implementer.fire(
            tenant_id=tenant_id,
            user_id=user_id,
            trigger_context=trigger_context,
        )


class _NoopSecurityEvents:
    def emit(self, event: object) -> None:
        pass


def _build_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("INTERNAL_SECRET", _SECRET)
    monkeypatch.setenv("OPERATOR_TIMEZONE", "UTC")
    monkeypatch.setenv("WEBHOOK_TENANT_ID", _TENANT_ID)

    audit = FakeAuditPort()
    fired = FakeFiredTriggersRepository()
    implementer = _StubImplementer()
    dispatch = _SyncBroadcastDispatch(implementer=implementer)

    # A frozen MessagingComposition needs all fields; only the
    # broadcast/idempotency surfaces are load-bearing for the trigger
    # endpoint, the rest are stubs.
    composition = MessagingComposition(
        repository=FakeMessageRepository(),
        delivery_port=FakeMessageDeliveryPort(),
        message_writer=None,  # type: ignore[arg-type]
        portfolio_gateway=None,  # type: ignore[arg-type]
        structured_output_port=None,  # type: ignore[arg-type]
        confidence_calculator=None,  # type: ignore[arg-type]
        cell_dispatch=None,  # type: ignore[arg-type]
        broadcast_dispatch=dispatch,
        broadcast_flow_registry=None,  # type: ignore[arg-type]
        fired_triggers_repository=fired,
        channel_resolver=StaticConfigChannelResolverAdapter(
            operator_default_channel=ChannelType.WHATSAPP,
            operator_default_address="+14155238886",
        ),
        pending_clarification_repository=None,  # type: ignore[arg-type]
        pending_clarification_reader=None,  # type: ignore[arg-type]
        threshold_resolver=None,  # type: ignore[arg-type]
        meta_classifier=None,  # type: ignore[arg-type]
        audit_event_reader=None,  # type: ignore[arg-type]
        portfolio_case_lookup=None,  # type: ignore[arg-type]
        mirror_portfolio_reader=None,  # type: ignore[arg-type]
        high_confidence_threshold=0.8,
        from_address="+14155238886",
        webhook_tenant_id=_TENANT_ID,
        webhook_jurisdiction="eu-west",
        webhook_url="",
        twilio_auth_token="token",
    )

    app = FastAPI()
    register_internal_secret_error_handlers(app)
    app.include_router(triggers_router.router)
    app.state.messaging = composition
    app.state.audit_port = audit
    app.state.security_events = _NoopSecurityEvents()
    client = TestClient(app)
    return client, audit, fired, implementer


def _fire_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "trigger_type": "daily_scheduled",
        "trigger_id": str(uuid4()),
        "triggered_at": "2026-05-28T06:00:00+00:00",
    }
    body.update(overrides)
    return body


def test_missing_internal_secret_rejected_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _audit, _fired, _impl = _build_client(monkeypatch)
    resp = client.post(_FIRE_PATH, json=_fire_body())
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "internal_secret_invalid"


def test_wrong_internal_secret_rejected_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _audit, _fired, _impl = _build_client(monkeypatch)
    resp = client.post(
        _FIRE_PATH,
        json=_fire_body(),
        headers={"X-Internal-Secret": "wrong"},
    )
    assert resp.status_code == 401


def test_fresh_fire_accepted_inserts_audits_dispatches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, audit, fired, impl = _build_client(monkeypatch)
    resp = client.post(
        _FIRE_PATH,
        json=_fire_body(),
        headers={"X-Internal-Secret": _SECRET},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"
    assert len(fired.inserted) == 1
    assert len(audit.events) == 1
    assert audit.events[0].action_verb == "messaging.broadcast.initiated"
    assert len(impl.fired) == 1
    assert impl.fired[0].trigger_type is BroadcastTriggerType.DAILY_SCHEDULED


def test_duplicate_fire_already_fired_no_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, audit, fired, impl = _build_client(monkeypatch)
    headers = {"X-Internal-Secret": _SECRET}
    first = client.post(_FIRE_PATH, json=_fire_body(), headers=headers)
    second = client.post(_FIRE_PATH, json=_fire_body(), headers=headers)
    assert first.json()["status"] == "accepted"
    assert second.status_code == 200
    assert second.json()["status"] == "already_fired"
    # only the first fire had side effects
    assert len(audit.events) == 1
    assert len(impl.fired) == 1


def test_unknown_trigger_type_unprocessable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _audit, _fired, _impl = _build_client(monkeypatch)
    resp = client.post(
        _FIRE_PATH,
        json=_fire_body(trigger_type="not_a_trigger"),
        headers={"X-Internal-Secret": _SECRET},
    )
    assert resp.status_code == 422
