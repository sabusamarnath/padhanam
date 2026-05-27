"""Integration tests for the messaging HTTP routes (D129, S45; S46).

Exercises the routes via TestClient over an in-memory composition:
the outbound send, the GET single and list surfaces, and the Twilio
WhatsApp webhook receiver. S46 extends the webhook coverage to the
manual entry cell end-to-end path — inbound webhook → signature
verification → ActorContext synthesis → cell.turn() → intent
extraction → target resolution → downstream orchestration → cited
response → outbound WhatsApp reply — with the cell's LLM and
portfolio collaborators stubbed in memory.

Tenant isolation is the adapter contract's concern and is exercised
by tests/contract/tenant_isolation/test_messaging_isolation.py
against real per-tenant databases; these route-level tests use
in-memory fakes.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from apps.api._auth_errors import register_auth_error_handlers
from apps.api._messaging_errors import register_messaging_error_handlers
from apps.api._messaging_wiring import MessagingComposition
from apps.api.middleware import get_actor_context
from apps.api.routers import messaging as messaging_router
from contexts.intake.application.ports.message_writer import MessageWriteResult
from contexts.messaging.application.ports.portfolio_gateway import (
    CaseSummary,
    CaseWriteOutcome,
    DataPointWriteOutcome,
)
from contexts.messaging.application.record_inbound_message import (
    record_inbound_message,
)
from contexts.messaging.domain import MessageChannel
from shared_kernel import ActorContext, StructuredOutputResponse, TenantContext
from shared_kernel.authorisation import (
    MESSAGING_MESSAGE_SEND,
    ROLE_OPERATOR,
    authorisations_for_roles,
)
from tests.unit.contexts.intake.application._fakes import FakeIntakeRepository
from tests.unit.contexts.messaging.application._fakes import (
    FakeAuditPort,
    FakeMessageDeliveryPort,
    FakeMessageRepository,
)

_TENANT_ID = "00000000-0000-4000-8000-00000000a001"
_AUTH_TOKEN = "test-twilio-auth-token-1234"
_WEBHOOK_PATH = "/api/v1/messaging/inbound"

_UNCLEAR = {
    "intent_type": "unclear",
    "clarification": "Could you say a little more?",
}


def _ctx() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_ID,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_ID,
    )


def _actor(*, full: bool = True) -> ActorContext:
    role_list = frozenset({ROLE_OPERATOR})
    granted = authorisations_for_roles(role_list)
    if not full:
        granted = frozenset(granted - {MESSAGING_MESSAGE_SEND})
    return ActorContext(
        tenant_context=_ctx(),
        actor_id="operator",
        role_list=role_list,
        authorisation_set=granted,
    )


class _NoopSecurityEvents:
    def emit(self, event: object) -> None:
        pass


class _FakeMirrorPortfolioReader:
    """Stub MirrorPortfolioReader for integration tests (S52).

    The route-level tests rarely route through mirror-conversation;
    the stub returns empty results so the cell composes a clean
    "no cases" response if mirror routing fires unexpectedly.
    """

    async def list_cases(self, *, actor, limit: int = 50):
        return ()

    async def get_case_detail(self, *, actor, case_id):
        return None

    async def get_data_point(self, *, actor, data_point_id):
        return None

    async def find_cases(self, *, actor):
        return ()


class _FakeAuditEventReader:
    """Stub AuditEventReader for integration tests (S52).

    The route-level integration tests usually exercise manual-entry-
    shaped inbounds; the audit-conversation runner is rarely the
    routing target. When it is, the stub returns an empty
    AuditEventListPage so the cell composes a clean no-results
    response.
    """

    async def get_audit_event(self, **kwargs):
        return None

    async def list_audit_events_with_filters(self, **kwargs):
        from contexts.audit.domain.chain_integrity import (
            ChainIntegrityVerification,
        )
        from contexts.audit.domain.query_filters import AuditEventListPage

        return AuditEventListPage(
            events=(),
            next_cursor=None,
            chain_integrity=ChainIntegrityVerification(status="verified"),
        )

    async def verify_chain_segment(self, **kwargs):
        from contexts.audit.domain.chain_integrity import (
            ChainIntegrityVerification,
        )
        return ChainIntegrityVerification(status="verified")


class _FakePendingClarificationRepository:
    """An in-memory PendingClarification repository for tests (S47)."""

    def __init__(self) -> None:
        self.pendings: dict[UUID, Any] = {}

    async def save(self, *, tenant_context, pending) -> None:
        self.pendings[pending.id] = pending

    async def update_status(self, *, tenant_context, pending) -> None:
        self.pendings[pending.id] = pending

    async def get_by_id(self, *, tenant_context, pending_id: UUID):
        return self.pendings.get(pending_id)

    async def get_active_for_user(self, *, tenant_context, user_id: str):
        for p in self.pendings.values():
            if (
                p.tenant_id == UUID(tenant_context.tenant_id)
                and p.user_id == user_id
                and p.status.value == "PENDING"
            ):
                return p
        return None


class _FakePendingClarificationReader:
    """Cell-facing read adapter wrapping the test repo (S47)."""

    def __init__(self, repository: _FakePendingClarificationRepository) -> None:
        self._repository = repository

    async def get_active(self, *, tenant_id: UUID, user_id: str):
        for p in self._repository.pendings.values():
            if (
                p.tenant_id == tenant_id
                and p.user_id == user_id
                and p.status.value == "PENDING"
            ):
                return p
        return None


class _SyncCellDispatch:
    """Test fake: synchronously await the cell so assertions see effects.

    The production InProcessCellDispatchAdapter wraps the cell in
    ``asyncio.create_task`` so the webhook returns 2xx promptly; the
    cell completes later on the event loop. That asynchrony makes
    side-effect assertions flaky in TestClient (the response can
    arrive before the task completes). This test fake honours the same
    dispatch port contract — including exception-captures-don't-raise
    — but awaits the cell inline so tests can assert on the cell's
    persisted side effects deterministically.
    """

    def __init__(self) -> None:
        self.dispatched: int = 0
        self.failed_contexts: list[dict[str, Any]] = []

    async def dispatch(
        self,
        cell_run: Any,
        *,
        context: dict[str, Any],
    ) -> None:
        self.dispatched += 1
        try:
            await cell_run()
        except Exception:
            self.failed_contexts.append(dict(context))


class _RecordingMessageWriter:
    """A MessageWriter port double that runs the real inbound use case."""

    def __init__(
        self, repository: FakeMessageRepository, audit_port: FakeAuditPort
    ) -> None:
        self._repository = repository
        self._audit_port = audit_port

    async def record_inbound_message(
        self,
        *,
        actor: ActorContext,
        channel: str,
        from_address: str,
        to_address: str,
        body: str,
        external_id: str | None,
        intake_id: UUID,
    ) -> MessageWriteResult:
        message = await record_inbound_message(
            repository=self._repository,
            audit_port=self._audit_port,
            actor=actor,
            channel=MessageChannel(channel),
            from_address=from_address,
            to_address=to_address,
            body=body,
            external_id=external_id,
            intake_id=intake_id,
        )
        return MessageWriteResult(
            message_id=message.id,
            direction=message.direction.value,
            channel=message.channel.value,
            body=message.body,
            from_address=message.from_address,
            to_address=message.to_address,
            status=message.status.value,
            external_id=message.external_id,
            intake_id=intake_id,
            created_at=message.created_at,
        )


class _FakeStructuredOutput:
    """Returns a preset intent extraction; optionally raises (S46).

    S52: a stub ``confidence`` of 0.95 lets the cell's confidence-aware
    composition (D134) take the high-confidence proceed path on
    ``create_case`` / ``add_data_point`` extractions; the UnclearIntent
    extractions still route as Case 3 because parse_intent of an
    ``unclear`` intent_type returns UnclearIntent regardless of
    confidence.
    """

    def __init__(
        self, extraction: dict[str, Any], *, fail: bool = False
    ) -> None:
        self._extraction = extraction
        self._fail = fail

    async def generate_structured(
        self, request: Any
    ) -> StructuredOutputResponse[dict[str, Any]]:
        if self._fail:
            raise RuntimeError("structured-output backend unavailable")
        return StructuredOutputResponse(
            value=self._extraction, confidence=0.95, provider_metadata={}
        )


class _FakePortfolioGateway:
    """An in-memory PortfolioGateway recording the cell's writes (S46)."""

    def __init__(self, *, cases: tuple[CaseSummary, ...] = ()) -> None:
        self._cases = cases
        self.created_cases: list[str] = []
        self.created_data_points: list[tuple[UUID, str]] = []
        self.revised: list[UUID] = []

    async def find_cases(self, *, actor: ActorContext):
        return self._cases

    async def find_data_points(self, *, actor: ActorContext):
        return ()

    async def create_case(self, *, actor, raw_text, title):
        self.created_cases.append(title)
        return CaseWriteOutcome(
            case_id=uuid4(), intake_id=uuid4(), title=title
        )

    async def create_data_point(
        self, *, actor, raw_text, case_id, data_point_type, value
    ):
        self.created_data_points.append((case_id, data_point_type))
        return DataPointWriteOutcome(
            data_point_id=uuid4(),
            case_id=case_id,
            intake_id=uuid4(),
            assertion_ids=(uuid4(),),
        )

    async def revise_data_point(self, *, actor, raw_text, data_point_id, value):
        self.revised.append(data_point_id)
        return DataPointWriteOutcome(
            data_point_id=data_point_id,
            case_id=uuid4(),
            intake_id=uuid4(),
            assertion_ids=(uuid4(), uuid4()),
        )


def _build(
    *,
    full_permissions: bool = True,
    extraction: dict[str, Any] | None = None,
    structured_output_fails: bool = False,
    gateway: _FakePortfolioGateway | None = None,
):
    """Build a test client plus the in-memory fakes behind it."""
    message_repo = FakeMessageRepository()
    delivery = FakeMessageDeliveryPort()
    audit = FakeAuditPort()
    intake_repo = FakeIntakeRepository()
    portfolio_gateway = gateway or _FakePortfolioGateway()
    cell_dispatch = _SyncCellDispatch()
    from contexts.inference.adapters.confidence_self_reported import (
        SelfReportedConfidenceAdapter,
    )
    from contexts.messaging.adapters.threshold_single_pair import (
        SinglePairThresholdResolverAdapter,
    )
    from shared_kernel import ConfidenceThresholds
    pending_repo = _FakePendingClarificationRepository()
    pending_reader = _FakePendingClarificationReader(pending_repo)
    # S52 (D140): MessagingComposition gains meta_classifier +
    # audit_event_reader + portfolio_case_lookup. The integration
    # tests run the dispatch substrate against the rule-based meta
    # classifier (deterministic, no LLM call) so existing scenarios
    # whose inbound matches manual-entry-shaped tokens continue to
    # route through manual_entry as before. Tests exercising the
    # dispatch flow directly live at the unit-test suite.
    from contexts.messaging.adapters.rule_based_meta_classifier import (
        RuleBasedMetaClassifierAdapter,
    )
    from apps.api._messaging_wiring import PortfolioCaseLookupAdapter

    # D143 + D144 (S53): one composite InProcessBroadcastDispatchAdapter
    # serves both BroadcastDispatch and BroadcastFlowRegistry surfaces;
    # the StaticConfigChannelResolverAdapter serves the ChannelResolver
    # consultation at the reactive outbound refactor.
    from contexts.messaging.adapters.channel_resolver.static_config_channel_resolver_adapter import (
        StaticConfigChannelResolverAdapter,
    )
    from contexts.messaging.adapters.dispatch.in_process_broadcast_dispatch_adapter import (
        InProcessBroadcastDispatchAdapter,
    )
    from contexts.messaging.domain.channel_type import ChannelType

    broadcast_dispatch_composite = InProcessBroadcastDispatchAdapter()
    composition = MessagingComposition(
        repository=message_repo,
        delivery_port=delivery,
        message_writer=_RecordingMessageWriter(message_repo, audit),
        portfolio_gateway=portfolio_gateway,
        structured_output_port=_FakeStructuredOutput(
            extraction or _UNCLEAR, fail=structured_output_fails
        ),
        confidence_calculator=SelfReportedConfidenceAdapter(),
        cell_dispatch=cell_dispatch,
        broadcast_dispatch=broadcast_dispatch_composite,
        broadcast_flow_registry=broadcast_dispatch_composite,
        channel_resolver=StaticConfigChannelResolverAdapter(
            operator_default_channel=ChannelType.WHATSAPP,
            operator_default_address="+14155238886",
        ),
        pending_clarification_repository=pending_repo,
        pending_clarification_reader=pending_reader,
        threshold_resolver=SinglePairThresholdResolverAdapter(
            thresholds=ConfidenceThresholds(high=0.8, medium=0.5),
        ),
        meta_classifier=RuleBasedMetaClassifierAdapter(),
        audit_event_reader=_FakeAuditEventReader(),
        portfolio_case_lookup=PortfolioCaseLookupAdapter(
            portfolio_gateway=portfolio_gateway,
        ),
        mirror_portfolio_reader=_FakeMirrorPortfolioReader(),
        high_confidence_threshold=0.8,
        from_address="+14155238886",
        webhook_tenant_id=_TENANT_ID,
        webhook_jurisdiction="eu-west",
        webhook_url="",
        twilio_auth_token=_AUTH_TOKEN,
    )
    app = FastAPI()
    register_auth_error_handlers(app)
    register_messaging_error_handlers(app)
    app.include_router(messaging_router.router)
    app.state.messaging = composition
    app.state.audit_port = audit
    app.state.intake_repository = intake_repo
    app.state.security_events = _NoopSecurityEvents()
    app.dependency_overrides[get_actor_context] = lambda: _actor(
        full=full_permissions
    )
    client = TestClient(app)
    return client, message_repo, delivery, audit, intake_repo, portfolio_gateway


# --- outbound send ---


def test_send_message_route_delivers_and_persists() -> None:
    client, message_repo, delivery, *_ = _build()
    resp = client.post(
        "/api/v1/messaging/send",
        json={"to_address": "+447700900123", "body": "your 3pm moved"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["direction"] == "OUTBOUND"
    assert body["channel"] == "WHATSAPP"
    assert body["to_address"] == "+447700900123"
    assert len(delivery.send_calls) == 1
    assert len(message_repo.messages) == 1


def test_send_message_route_denied_without_permission() -> None:
    client, *_ = _build(full_permissions=False)
    resp = client.post(
        "/api/v1/messaging/send",
        json={"to_address": "+447700900123", "body": "blocked"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "authorisation_denied"


# --- GET single and list ---


def test_get_message_route_round_trip() -> None:
    client, *_ = _build()
    sent = client.post(
        "/api/v1/messaging/send",
        json={"to_address": "+447700900123", "body": "hello"},
    ).json()
    fetched = client.get(f"/api/v1/messaging/messages/{sent['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == sent["id"]


def test_get_message_route_absent_returns_404() -> None:
    client, *_ = _build()
    resp = client.get(f"/api/v1/messaging/messages/{uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "message_not_found"


def test_list_messages_route_returns_sent_messages() -> None:
    client, *_ = _build()
    client.post(
        "/api/v1/messaging/send",
        json={"to_address": "+447700900123", "body": "one"},
    )
    resp = client.get("/api/v1/messaging/messages")
    assert resp.status_code == 200
    assert len(resp.json()["messages"]) == 1


# --- inbound webhook ---


def _inbound_form(body: str = "status: Acme deal moved to legal review"):
    return {
        "From": "whatsapp:+447700900123",
        "To": "whatsapp:+14155238886",
        "Body": body,
        "MessageSid": "SMinbound0001",
    }


def _post_webhook(client: TestClient, form: dict[str, str]):
    url = f"http://testserver{_WEBHOOK_PATH}"
    signature = RequestValidator(_AUTH_TOKEN).compute_signature(url, form)
    return client.post(
        _WEBHOOK_PATH, data=form, headers={"X-Twilio-Signature": signature}
    )


def test_inbound_webhook_records_inbound_then_runs_cell() -> None:
    """A valid webhook records the inbound message and IntakeRecord,
    then runs the cell — which replies with an outbound message."""
    client, message_repo, delivery, _audit, intake_repo, _gw = _build()
    resp = _post_webhook(client, _inbound_form())

    assert resp.status_code == 200
    assert resp.json()["status"] == "received"
    # the inbound landed as one IntakeRecord (WHATSAPP_INBOUND) ...
    assert len(intake_repo.intakes) == 1
    # ... and the webhook persisted both the inbound message and the
    # cell's outbound reply.
    directions = sorted(m.direction.value for m in message_repo.messages.values())
    assert directions == ["INBOUND", "OUTBOUND"]
    assert len(delivery.send_calls) == 1


def test_inbound_webhook_create_case_intent_drives_cell_and_replies() -> None:
    gateway = _FakePortfolioGateway()
    client, message_repo, delivery, _audit, _intake, gw = _build(
        extraction={
            "intent_type": "create_case",
            "title": "Q3 portfolio review",
            "case_reference": "",
            "data_point_type": "",
            "data_point_reference": "",
            "value_text": "",
            "clarification": "",
        },
        gateway=gateway,
    )
    # S52 (D140): the rule-based meta-classifier routes "create a
    # case" by token match to manual_entry at high confidence; the
    # cell then runs and creates the case.
    resp = _post_webhook(
        client, _inbound_form("create a case for the Q3 portfolio review")
    )

    assert resp.status_code == 200
    assert gw.created_cases == ["Q3 portfolio review"]
    outbound = next(
        m for m in message_repo.messages.values()
        if m.direction.value == "OUTBOUND"
    )
    assert "Recorded a new case" in outbound.body
    # D131: the cited confirmation renders a compact citation line.
    assert "ref " in outbound.body and "intake " in outbound.body


def test_inbound_webhook_unclear_intent_replies_with_clarification() -> None:
    """Cell-level UnclearIntent surfaces 'Could you say a little more?'.

    S52 (D140): the meta-classifier routes the inbound on the
    manual-entry-shaped 'add' token, so the manual_entry cell runs.
    The cell's stubbed structured-output returns UnclearIntent and
    the cell renders the cell-altitude clarification (distinct from
    the dispatch-altitude clarification at D140 Step 5).
    """
    client, message_repo, _delivery, _audit, _intake, gw = _build(
        extraction=_UNCLEAR
    )
    resp = _post_webhook(client, _inbound_form("add a thing"))

    assert resp.status_code == 200
    assert gw.created_cases == []
    outbound = next(
        m for m in message_repo.messages.values()
        if m.direction.value == "OUTBOUND"
    )
    assert outbound.body == "Could you say a little more?"


def test_inbound_webhook_dispatch_ambiguous_surfaces_routing_prompt() -> None:
    """S52 (D140 Step 5): dispatch-ambiguous inbounds surface the routing prompt.

    The default _inbound_form() body ('status: Acme deal moved to legal
    review') matches none of the rule-based meta-classifier's token
    sets and falls through to the low-confidence default. Step 5 of
    the dispatch flow creates a dispatch_clarification PendingClarification
    and sends the numbered routing prompt to the operator. The cell
    does not run.
    """
    client, message_repo, _delivery, _audit, _intake, gw = _build()
    resp = _post_webhook(client, _inbound_form())

    assert resp.status_code == 200
    assert gw.created_cases == []
    outbound = next(
        m for m in message_repo.messages.values()
        if m.direction.value == "OUTBOUND"
    )
    assert "Record new portfolio state" in outbound.body
    assert "audit history" in outbound.body
    assert "current portfolio state" in outbound.body


def test_inbound_webhook_cell_failure_still_returns_200() -> None:
    """A cell failure must not turn the webhook non-2xx — that would
    make Twilio retry and duplicate the already-persisted inbound.

    S52 (D140): the rule-based meta-classifier does not consume
    structured_output, so dispatch routes on the inbound's "add"
    token to manual_entry at high confidence. The manual_entry cell
    then attempts intent extraction, which fails because the test's
    StructuredOutput stub is in fail mode. The CellDispatch port's
    failure-capture catches the exception so the webhook returns 200
    with the inbound message still persisted as the canonical
    record-of-arrival; no outbound is sent because the cell never
    composed a reply.
    """
    client, message_repo, _delivery, _audit, intake_repo, _gw = _build(
        structured_output_fails=True
    )
    resp = _post_webhook(client, _inbound_form("add a goal"))

    assert resp.status_code == 200
    # The inbound was still recorded; only the cell reply was lost.
    assert len(intake_repo.intakes) == 1
    assert len(message_repo.messages) == 1


def test_inbound_webhook_invalid_signature_rejected() -> None:
    client, message_repo, _delivery, _audit, intake_repo, _gw = _build()
    resp = client.post(
        _WEBHOOK_PATH,
        data=_inbound_form(),
        headers={"X-Twilio-Signature": "not-a-valid-signature"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "webhook_signature_invalid"
    # the rejected webhook wrote nothing
    assert len(intake_repo.intakes) == 0
    assert len(message_repo.messages) == 0
