"""Route tests for the live conversation surface (D158, S59).

A bare FastAPI app carries the conversation router with a fake messaging
composition + audit port on app.state; ``get_actor_context`` is
dependency-overridden. Exercises the open + turn endpoints' HTTP DTO shape
(reply, threaded ConversationState, citation chips), the 404 on a missing
focus Case, and the 422 on an unsupported focus kind — over HTTP, no auth
middleware (the authentication path is tested elsewhere).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.middleware import get_actor_context
from apps.api.routers import conversation as conversation_router
from apps.api.routers.messaging import get_audit_port, get_messaging_composition
from contexts.mirror_conversation.application.ports.mirror_portfolio_reader import (  # noqa: E501
    MirrorCaseDetail,
    MirrorCaseSummary,
)
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import authorisations_for_roles

_TENANT = "00000000-0000-4000-8000-00000000a001"
_NOW = datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc)


def _actor() -> ActorContext:
    roles = frozenset({"operator"})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
        ),
        actor_id="operator-001",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


class _Reader:
    def __init__(self, detail: MirrorCaseDetail | None) -> None:
        self._detail = detail

    async def get_case_detail(self, *, actor, case_id):
        if self._detail is None or self._detail.case.case_id != case_id:
            return None
        return self._detail

    async def find_cases(self, *, actor):
        return (self._detail.case,) if self._detail else ()

    async def list_cases(self, *, actor, limit: int = 50):
        return (self._detail.case,) if self._detail else ()

    async def get_data_point(self, *, actor, data_point_id):
        return None


class _Structured:
    def __init__(self, value: dict) -> None:
        self._value = value

    async def generate_structured(self, request):
        from shared_kernel import StructuredOutputResponse

        return StructuredOutputResponse(
            value=self._value, confidence=0.95, provider_metadata={}
        )


class _Confidence:
    def compute(self, *, request, response) -> float:
        return 0.95


class _PendingReader:
    async def get_active(self, *, tenant_id, user_id):
        return None


class _PendingRepo:
    async def save(self, *, tenant_context, pending) -> None:
        return None

    async def update_status(self, *, tenant_context, pending) -> None:
        return None

    async def get_by_id(self, *, tenant_context, pending_id):
        return None

    async def get_active_for_user(self, *, tenant_context, user_id):
        return None


class _Audit:
    async def emit(self, event):
        return event


class _Messaging:
    def __init__(self, reader: _Reader, value: dict) -> None:
        from contexts.messaging.adapters.threshold_single_pair import (
            SinglePairThresholdResolverAdapter,
        )
        from shared_kernel import ConfidenceThresholds

        self.mirror_portfolio_reader = reader
        self.structured_output_port = _Structured(value)
        self.confidence_calculator = _Confidence()
        self.threshold_resolver = SinglePairThresholdResolverAdapter(
            thresholds=ConfidenceThresholds(high=0.8, medium=0.5),
        )
        self.pending_clarification_reader = _PendingReader()
        self.pending_clarification_repository = _PendingRepo()


def _detail(title: str) -> MirrorCaseDetail:
    case = MirrorCaseSummary(
        case_id=uuid4(),
        title=title,
        case_status="OPEN",
        created_at=_NOW,
        last_activity_at=_NOW,
        data_point_count=0,
    )
    return MirrorCaseDetail(case=case, data_points=())


def _client(messaging: _Messaging) -> TestClient:
    app = FastAPI()
    app.include_router(conversation_router.router)
    app.state.messaging = messaging
    app.state.audit_port = _Audit()
    app.dependency_overrides[get_actor_context] = _actor
    app.dependency_overrides[get_messaging_composition] = lambda: messaging
    app.dependency_overrides[get_audit_port] = lambda: app.state.audit_port
    return TestClient(app)


def test_open_returns_reply_and_threaded_state() -> None:
    detail = _detail("Q3 portfolio review")
    messaging = _Messaging(
        _Reader(detail),
        {
            "intent_class": "show_case",
            "case_reference": "Q3 portfolio review",
            "data_point_reference": "",
            "child_reference": "",
            "confidence": 0.95,
            "clarification": "",
        },
    )
    client = _client(messaging)
    res = client.post(
        "/api/v1/daily-driver/conversation/open",
        json={"focus_kind": "CASE", "focus_id": str(detail.case.case_id)},
    )
    assert res.status_code == 200
    body = res.json()
    assert "Q3 portfolio review" in body["reply"]
    assert body["state"]["conversation_id"]
    assert body["state"]["turn_count"] == 1
    assert body["state"]["is_open"] is True
    # The focus threads back for the next turn.
    assert body["state"]["cell_payload"]["current_focus_artefact"]["artefact_type"] == "case"
    # Citation chips carry human labels, never the raw UUID; the reply text
    # and chip labels/refs are the rendered surface (the cell_payload is an
    # opaque client-threaded focus token, D141, not surfaced to the user).
    assert any(c["type"] == "case" for c in body["citations"])
    full_uuid = str(detail.case.case_id)
    assert full_uuid not in body["reply"]
    for c in body["citations"]:
        assert full_uuid not in c["label"]
        assert full_uuid not in c["ref"]


def test_open_missing_case_returns_404() -> None:
    messaging = _Messaging(_Reader(None), {"intent_class": "unclear_mirror"})
    client = _client(messaging)
    res = client.post(
        "/api/v1/daily-driver/conversation/open",
        json={"focus_kind": "CASE", "focus_id": str(uuid4())},
    )
    assert res.status_code == 404


def test_open_unsupported_focus_kind_returns_422() -> None:
    messaging = _Messaging(_Reader(None), {"intent_class": "unclear_mirror"})
    client = _client(messaging)
    res = client.post(
        "/api/v1/daily-driver/conversation/open",
        json={"focus_kind": "COMMITMENT", "focus_id": str(uuid4())},
    )
    assert res.status_code == 422


def test_open_routes_calendar_focus_to_the_calendar_path(monkeypatch) -> None:
    """focus_kind=CALENDAR dispatches to the calendar cell path (D159).

    The infra wrapper builds per-tenant infrastructure (DB), so the route's
    dispatch is verified by stubbing the wiring function; the calendar
    logic itself is unit-tested in test_conversation_cell.py.
    """
    from apps.api._conversation_cell_wiring import ConversationTurnResult

    seen: dict = {}

    async def _fake_open_calendar(*, messaging, audit_port, actor, focus_id):
        seen["focus_id"] = focus_id
        return ConversationTurnResult(
            conversation_id="conv-cal",
            purpose="calendar_query",
            turn_count=1,
            is_open=True,
            cell_payload=None,
            reply="Board call, today 15:00",
            citations=[],
        )

    monkeypatch.setattr(
        conversation_router, "open_calendar_conversation", _fake_open_calendar
    )
    messaging = _Messaging(_Reader(None), {"intent_class": "unclear_mirror"})
    client = _client(messaging)
    focus_id = uuid4()
    res = client.post(
        "/api/v1/daily-driver/conversation/open",
        json={"focus_kind": "CALENDAR", "focus_id": str(focus_id)},
    )
    assert res.status_code == 200
    assert res.json()["state"]["purpose"] == "calendar_query"
    assert seen["focus_id"] == focus_id


def test_open_calendar_missing_meeting_returns_404(monkeypatch) -> None:
    async def _none(*, messaging, audit_port, actor, focus_id):
        return None

    monkeypatch.setattr(
        conversation_router, "open_calendar_conversation", _none
    )
    messaging = _Messaging(_Reader(None), {"intent_class": "unclear_mirror"})
    client = _client(messaging)
    res = client.post(
        "/api/v1/daily-driver/conversation/open",
        json={"focus_kind": "CALENDAR", "focus_id": str(uuid4())},
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "meeting not found"


def test_turn_routes_calendar_purpose_to_the_calendar_path(monkeypatch) -> None:
    from apps.api._conversation_cell_wiring import ConversationTurnResult

    async def _fake_advance_calendar(
        *, messaging, audit_port, actor, conversation_id, purpose, turn_count, text
    ):
        return ConversationTurnResult(
            conversation_id=conversation_id,
            purpose="calendar_query",
            turn_count=turn_count + 1,
            is_open=True,
            cell_payload=None,
            reply="2 meetings today",
            citations=[],
        )

    monkeypatch.setattr(
        conversation_router,
        "advance_calendar_conversation",
        _fake_advance_calendar,
    )
    messaging = _Messaging(_Reader(None), {"intent_class": "unclear_mirror"})
    client = _client(messaging)
    res = client.post(
        "/api/v1/daily-driver/conversation/turn",
        json={
            "state": {
                "conversation_id": "conv-cal",
                "purpose": "calendar_query",
                "turn_count": 1,
                "is_open": True,
                "cell_payload": None,
            },
            "text": "what's on today",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["state"]["purpose"] == "calendar_query"
    assert body["state"]["turn_count"] == 2
    assert body["reply"] == "2 meetings today"


def test_turn_advances_from_threaded_state() -> None:
    detail = _detail("Q3 portfolio review")
    messaging = _Messaging(
        _Reader(detail),
        {
            "intent_class": "list_cases",
            "case_reference": "",
            "data_point_reference": "",
            "child_reference": "",
            "confidence": 0.95,
            "clarification": "",
        },
    )
    client = _client(messaging)
    res = client.post(
        "/api/v1/daily-driver/conversation/turn",
        json={
            "state": {
                "conversation_id": "conv-1",
                "purpose": "mirror_query",
                "turn_count": 1,
                "is_open": True,
                "cell_payload": None,
            },
            "text": "list my cases",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["state"]["conversation_id"] == "conv-1"
    assert body["state"]["turn_count"] == 2
