"""Unit tests for the dispatch_inbound use case (D140, S52).

Five tests cover the five-step dispatch flow plus the
dispatch_clarification resolution path. Stubs for ports keep the
test surface narrow and the assertions structural.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from contexts.audit.domain.events import AuditEvent

from contexts.messaging.application import dispatch_inbound
from contexts.messaging.application.dispatch_inbound import DispatchContext
from contexts.messaging.application.ports.meta_classifier import (
    ConversationTurn,
    MetaClassificationResult,
)
from contexts.messaging.domain.cell_identifier import CellIdentifier
from contexts.messaging.domain.message import (
    Message,
    MessageChannel,
    MessageDirection,
    MessageStatus,
)
from contexts.messaging.domain.pending_clarification import (
    PendingClarification,
    PendingClarificationStatus,
)
from contexts.messaging.ports.message_delivery_port import DeliveryResult
from shared_kernel import (
    ActorContext,
    StructuredOutputParseFailure,
    TenantContext,
)
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles


_TENANT_ID = "00000000-0000-4000-8000-00000000a001"
_USER_ID = "operator"
_REPLY_TO = "+447700900123"
_FROM_ADDRESS = "+14155238886"
_HIGH_THRESHOLD = 0.8


def _actor() -> ActorContext:
    tc = TenantContext(
        tenant_id=_TENANT_ID,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_ID,
    )
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=tc,
        actor_id=_USER_ID,
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def _context(inbound_text: str = "Show me Q3") -> DispatchContext:
    return DispatchContext(
        tenant_id=UUID(_TENANT_ID),
        user_id=_USER_ID,
        inbound_text=inbound_text,
        inbound_intake_id=uuid4(),
        reply_to=_REPLY_TO,
        conversation_history=(),
    )


class _StubPendingReader:
    def __init__(self, active: PendingClarification | None = None) -> None:
        self.active = active

    async def get_active(
        self, *, tenant_id: UUID, user_id: str
    ) -> PendingClarification | None:
        return self.active


class _StubPendingRepo:
    def __init__(self) -> None:
        self.saved: list[PendingClarification] = []
        self.status_updates: list[PendingClarification] = []
        self._active: PendingClarification | None = None

    async def save(self, *, tenant_context, pending) -> None:
        self.saved.append(pending)
        self._active = pending

    async def update_status(self, *, tenant_context, pending) -> None:
        self.status_updates.append(pending)
        if pending.status is not PendingClarificationStatus.PENDING:
            self._active = None

    async def get_by_id(self, *, tenant_context, pending_id) -> Any:
        return None

    async def get_active_for_user(
        self, *, tenant_context, user_id: str
    ) -> PendingClarification | None:
        return self._active


class _StubMetaClassifier:
    def __init__(self, *, result=None, raise_parse_failure: bool = False) -> None:
        self._result = result
        self._raise = raise_parse_failure

    async def classify(
        self,
        *,
        tenant_id,
        inbound_text,
        conversation_history=(),
    ) -> MetaClassificationResult:
        if self._raise:
            raise StructuredOutputParseFailure("bad parse")
        return self._result


class _ImmediateCellDispatch:
    """CellDispatch that awaits the cell_run synchronously for test observability."""

    def __init__(self) -> None:
        self.dispatched: list[dict[str, Any]] = []

    async def dispatch(self, cell_run, *, context):
        self.dispatched.append(context)
        # Run inline so assertions can observe the cell's effects.
        await cell_run()


class _StubAuditPort:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def emit(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        return event


class _RecordingMessageRepo:
    def __init__(self) -> None:
        self.saved: list[Message] = []

    async def save(self, *, tenant_context, message: Message) -> None:
        self.saved.append(message)

    async def get_by_id(self, *, tenant_context, message_id):
        for m in self.saved:
            if m.id == message_id:
                return m
        return None

    async def list_for_tenant(
        self, *, tenant_context, filters, cursor, page_size
    ):
        raise AssertionError("not exercised by dispatch_inbound")


class _StubDeliveryPort:
    def __init__(self) -> None:
        self.sends: list[dict[str, Any]] = []

    async def send(self, *, channel, from_address, to_address, body):
        self.sends.append(
            {
                "channel": channel,
                "from": from_address,
                "to": to_address,
                "body": body,
            }
        )
        return DeliveryResult(
            status=MessageStatus.SENT, external_id=f"stub-{uuid4()}"
        )


class _RecordingCellRunner:
    def __init__(self) -> None:
        self.invocations: list[DispatchContext] = []

    async def __call__(self, context: DispatchContext) -> None:
        self.invocations.append(context)


def _pending_for_cell(
    target_cell: str,
    *,
    proposed_intent: dict[str, Any] | None = None,
) -> PendingClarification:
    now = datetime.now(timezone.utc)
    return PendingClarification(
        id=uuid4(),
        tenant_id=UUID(_TENANT_ID),
        jurisdiction="eu-west",
        user_id=_USER_ID,
        originating_channel="WHATSAPP",
        originating_user_address=_REPLY_TO,
        originating_intake_id=uuid4(),
        proposed_intent=proposed_intent or {"intent_class": "find_by_case"},
        proposed_action_summary="re-route a prior inbound",
        status=PendingClarificationStatus.PENDING,
        target_cell=target_cell,
        created_at=now,
        expires_at=now + timedelta(hours=24),
    )


def _make_runners() -> dict[CellIdentifier, _RecordingCellRunner]:
    return {
        CellIdentifier.MANUAL_ENTRY: _RecordingCellRunner(),
        CellIdentifier.AUDIT_CONVERSATION: _RecordingCellRunner(),
        CellIdentifier.MIRROR_CONVERSATION: _RecordingCellRunner(),
    }


def _run(coro) -> Any:
    return asyncio.run(coro)


# ----------------------------------------------- Step-1 / Step-2: active pending


def test_step2_routes_active_pending_to_named_cell() -> None:
    """An active manual_entry pending routes the next inbound to manual_entry."""
    active = _pending_for_cell("manual_entry")
    reader = _StubPendingReader(active=active)
    runners = _make_runners()

    routed = _run(
        dispatch_inbound.execute(
            context=_context("yes"),
            actor=_actor(),
            pending_reader=reader,
            pending_repository=_StubPendingRepo(),
            meta_classifier=_StubMetaClassifier(
                result=MetaClassificationResult(
                    cell_identifier=CellIdentifier.MIRROR_CONVERSATION,
                    confidence=0.95,
                ),
            ),
            high_confidence_threshold=_HIGH_THRESHOLD,
            cell_dispatch=_ImmediateCellDispatch(),
            audit_port=_StubAuditPort(),
            cell_runners=runners,
            message_repository=_RecordingMessageRepo(),
            delivery_port=_StubDeliveryPort(),
            from_address=_FROM_ADDRESS,
        )
    )

    assert routed is CellIdentifier.MANUAL_ENTRY
    assert len(runners[CellIdentifier.MANUAL_ENTRY].invocations) == 1
    assert len(runners[CellIdentifier.MIRROR_CONVERSATION].invocations) == 0


# ----------------------------------------------- Step-4: high-confidence dispatch


def test_step4_high_confidence_routes_to_classified_cell() -> None:
    reader = _StubPendingReader(active=None)
    runners = _make_runners()

    routed = _run(
        dispatch_inbound.execute(
            context=_context("Show me the Q3 portfolio review"),
            actor=_actor(),
            pending_reader=reader,
            pending_repository=_StubPendingRepo(),
            meta_classifier=_StubMetaClassifier(
                result=MetaClassificationResult(
                    cell_identifier=CellIdentifier.MIRROR_CONVERSATION,
                    confidence=0.92,
                ),
            ),
            high_confidence_threshold=_HIGH_THRESHOLD,
            cell_dispatch=_ImmediateCellDispatch(),
            audit_port=_StubAuditPort(),
            cell_runners=runners,
            message_repository=_RecordingMessageRepo(),
            delivery_port=_StubDeliveryPort(),
            from_address=_FROM_ADDRESS,
        )
    )

    assert routed is CellIdentifier.MIRROR_CONVERSATION
    assert len(runners[CellIdentifier.MIRROR_CONVERSATION].invocations) == 1


# ----------------------------------------------- Step-5: low-confidence clarification


def test_step5_low_confidence_creates_dispatch_clarification_and_replies() -> None:
    reader = _StubPendingReader(active=None)
    repo = _StubPendingRepo()
    delivery = _StubDeliveryPort()
    message_repo = _RecordingMessageRepo()

    routed = _run(
        dispatch_inbound.execute(
            context=_context("Q3 results"),
            actor=_actor(),
            pending_reader=reader,
            pending_repository=repo,
            meta_classifier=_StubMetaClassifier(
                result=MetaClassificationResult(
                    cell_identifier=CellIdentifier.MANUAL_ENTRY,
                    confidence=0.3,
                ),
            ),
            high_confidence_threshold=_HIGH_THRESHOLD,
            cell_dispatch=_ImmediateCellDispatch(),
            audit_port=_StubAuditPort(),
            cell_runners=_make_runners(),
            message_repository=message_repo,
            delivery_port=delivery,
            from_address=_FROM_ADDRESS,
        )
    )

    assert routed is CellIdentifier.DISPATCH_CLARIFICATION
    # A pending was persisted with target_cell='dispatch_clarification'.
    assert any(
        p.target_cell == CellIdentifier.DISPATCH_CLARIFICATION.value
        for p in repo.saved
    )
    # The original inbound text rides on the pending so the next reply
    # can re-route it.
    saved = next(
        p for p in repo.saved
        if p.target_cell == CellIdentifier.DISPATCH_CLARIFICATION.value
    )
    assert saved.proposed_intent["original_inbound_text"] == "Q3 results"
    # A clarification message was sent to the operator.
    assert len(delivery.sends) == 1
    assert "1." in delivery.sends[0]["body"]  # the numbered routing prompt


# ----------------------------------------------- Step-5: parse failure path


def test_step5_parse_failure_creates_dispatch_clarification() -> None:
    repo = _StubPendingRepo()
    routed = _run(
        dispatch_inbound.execute(
            context=_context("anything new on Q3?"),
            actor=_actor(),
            pending_reader=_StubPendingReader(active=None),
            pending_repository=repo,
            meta_classifier=_StubMetaClassifier(raise_parse_failure=True),
            high_confidence_threshold=_HIGH_THRESHOLD,
            cell_dispatch=_ImmediateCellDispatch(),
            audit_port=_StubAuditPort(),
            cell_runners=_make_runners(),
            message_repository=_RecordingMessageRepo(),
            delivery_port=_StubDeliveryPort(),
            from_address=_FROM_ADDRESS,
        )
    )
    assert routed is CellIdentifier.DISPATCH_CLARIFICATION
    assert any(
        p.target_cell == CellIdentifier.DISPATCH_CLARIFICATION.value
        for p in repo.saved
    )


# ----------------------- dispatch_clarification resolution: recognised reply


def test_dispatch_clarification_resolution_routes_to_chosen_cell() -> None:
    """Operator types 'mirror' against an active dispatch_clarification pending."""
    original_intake_id = uuid4()
    active = _pending_for_cell(
        "dispatch_clarification",
        proposed_intent={
            "purpose": "dispatch_clarification",
            "original_inbound_text": "Q3 results",
            "original_intake_id": str(original_intake_id),
        },
    )
    reader = _StubPendingReader(active=active)
    repo = _StubPendingRepo()
    repo._active = active
    runners = _make_runners()

    routed = _run(
        dispatch_inbound.execute(
            context=_context("mirror"),
            actor=_actor(),
            pending_reader=reader,
            pending_repository=repo,
            meta_classifier=_StubMetaClassifier(),
            high_confidence_threshold=_HIGH_THRESHOLD,
            cell_dispatch=_ImmediateCellDispatch(),
            audit_port=_StubAuditPort(),
            cell_runners=runners,
            message_repository=_RecordingMessageRepo(),
            delivery_port=_StubDeliveryPort(),
            from_address=_FROM_ADDRESS,
        )
    )

    assert routed is CellIdentifier.MIRROR_CONVERSATION
    # The dispatched cell sees the ORIGINAL inbound text, not "mirror".
    assert len(runners[CellIdentifier.MIRROR_CONVERSATION].invocations) == 1
    invoked_context = runners[CellIdentifier.MIRROR_CONVERSATION].invocations[0]
    assert invoked_context.inbound_text == "Q3 results"
    assert invoked_context.inbound_intake_id == original_intake_id
    # The prior dispatch_clarification pending expired.
    assert any(
        p.status is PendingClarificationStatus.EXPIRED
        for p in repo.status_updates
    )


# ----------------------- dispatch_clarification resolution: unrecognised reply


def test_dispatch_clarification_resolution_reprompts_on_unrecognised_reply() -> None:
    active = _pending_for_cell(
        "dispatch_clarification",
        proposed_intent={
            "purpose": "dispatch_clarification",
            "original_inbound_text": "Q3 results",
            "original_intake_id": str(uuid4()),
        },
    )
    reader = _StubPendingReader(active=active)
    repo = _StubPendingRepo()
    repo._active = active
    delivery = _StubDeliveryPort()
    runners = _make_runners()

    routed = _run(
        dispatch_inbound.execute(
            context=_context("hello there"),
            actor=_actor(),
            pending_reader=reader,
            pending_repository=repo,
            meta_classifier=_StubMetaClassifier(),
            high_confidence_threshold=_HIGH_THRESHOLD,
            cell_dispatch=_ImmediateCellDispatch(),
            audit_port=_StubAuditPort(),
            cell_runners=runners,
            message_repository=_RecordingMessageRepo(),
            delivery_port=delivery,
            from_address=_FROM_ADDRESS,
        )
    )

    assert routed is CellIdentifier.DISPATCH_CLARIFICATION
    # No real cell ran.
    for r in runners.values():
        assert r.invocations == []
    # A fresh routing prompt was delivered.
    assert len(delivery.sends) == 1
    assert "1." in delivery.sends[0]["body"]
