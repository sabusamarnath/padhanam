"""HTTP routes for the messaging context (D119, D129, S45).

Four routes:

- ``POST /api/v1/messaging/send`` — send an outbound WhatsApp message.
- ``POST /api/v1/messaging/inbound`` — the Twilio WhatsApp webhook
  receiver. It verifies the ``X-Twilio-Signature`` before processing
  and synthesises an operator ActorContext (Twilio webhooks carry no
  Padhanam Principal), then drives the
  ``record_intake_and_record_inbound_message`` orchestration.
- ``GET /api/v1/messaging/messages/{message_id}`` — single-record read.
- ``GET /api/v1/messaging/messages`` — paginated, filtered list.

The three authenticated routes resolve a request-scoped
``ActorContext`` via ``get_actor_context``. The webhook bypasses
bearer auth (its path is in the middleware's public-path set); its
authentication is the Twilio signature.
"""

from __future__ import annotations

import urllib.parse
from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request

from apps.api._errors import BoundTenantIdMismatchError
from apps.api._messaging_errors import MessageNotFoundError, WebhookSignatureError
from apps.api._messaging_wiring import MessagingComposition
from apps.api.middleware import get_actor_context
from apps.api.routers._messaging_dto import (
    InboundWebhookAck,
    MessageListResponse,
    MessageResponse,
    SendMessageRequest,
    message_list_to_response,
    message_to_response,
    webhook_ack,
)
from apps.api.routers._messaging_query import parse_message_list_query
from contexts.audit.domain.ports import AuditPort
from contexts.audit_conversation.application.cell import AuditConversationCell
from contexts.audit_conversation.application.response import (
    render_for_whatsapp as render_audit_for_whatsapp,
)
from apps.cli._calendar import build_calendar_refresh_adapter
from apps.cli._runtime import build_tenant_wiring
from contexts.calendar.adapters.outbound.postgres._tables import (
    connections as calendar_connections_table,
)
from contexts.calendar.adapters.outbound.postgres.meeting_store import (
    PostgresMeetingStore,
)
from contexts.calendar_conversation.application.cell import (
    CalendarConversationCell,
)
from contexts.calendar_conversation.application.response import (
    render_for_whatsapp as render_calendar_for_whatsapp,
)
from contexts.mirror_conversation.application.cell import (
    MirrorConversationCell,
)
from contexts.mirror_conversation.application.response import (
    extract_focus_from_cell_payload,
    render_for_whatsapp as render_mirror_for_whatsapp,
)
from contexts.intake.application.record_intake_and_record_inbound_message import (  # noqa: E501
    record_intake_and_record_inbound_message,
)
from contexts.intake.ports.intake_repository import IntakeRepository
from contexts.messaging.application import dispatch_inbound
from contexts.messaging.application.dispatch_inbound import DispatchContext
from contexts.messaging.application.cursor import encode_message_cursor
from contexts.messaging.application.get_message import get_message
from contexts.messaging.application.list_messages import list_messages
from contexts.messaging.application.manual_entry_cell import ManualEntryCell
from contexts.messaging.application.ports.meta_classifier import (
    ConversationTurn,
)
from contexts.messaging.application.send_message import send_message
from contexts.messaging.domain import MessageChannel, MessageDirection
from contexts.messaging.domain.cell_identifier import CellIdentifier
from contexts.messaging.domain.query_filters import (
    MessageListCursor,
    MessageListFilters,
)
from shared_kernel import (
    ActorContext,
    ConversationClosure,
    ConversationInput,
    ConversationInvocation,
    TenantContext,
    TenantId,
)
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles


# Recent-history window the meta-classifier and the mirror-conversation
# cell consume. Six turns covers the typical drill-down scope at Phase
# 2-A without bloating the LLM prompt.
_CONVERSATION_HISTORY_WINDOW = 6

router = APIRouter(prefix="/api/v1/messaging", tags=["messaging"])


def get_messaging_composition(request: Request) -> MessagingComposition:
    """FastAPI dependency: pull the messaging composition off app.state."""
    composition = getattr(request.app.state, "messaging", None)
    if composition is None:
        raise HTTPException(
            status_code=503,
            detail="messaging is not configured on this API instance",
        )
    return composition


def get_audit_port(request: Request) -> AuditPort:
    """FastAPI dependency: pull the configured AuditPort off app.state."""
    port = getattr(request.app.state, "audit_port", None)
    if port is None:
        raise HTTPException(
            status_code=503,
            detail="audit port not configured on this API instance",
        )
    return port


def get_intake_repository(request: Request) -> IntakeRepository:
    """FastAPI dependency: pull the configured IntakeRepository off app.state."""
    repo = getattr(request.app.state, "intake_repository", None)
    if repo is None:
        raise HTTPException(
            status_code=503,
            detail="intake repository not configured on this API instance",
        )
    return repo


def _synthesise_webhook_actor(
    messaging: MessagingComposition,
) -> ActorContext:
    """Synthesise an operator ActorContext for the inbound webhook.

    Twilio webhooks carry no Padhanam Principal; the webhook is a
    fixed-tenant unauthenticated-by-bearer ingress at Phase 2-A (its
    authentication is the X-Twilio-Signature). The receiver
    synthesises an operator ActorContext for the configured webhook
    tenant, mirroring the CLI's ActorContext synthesis. Multi-tenant
    webhook routing is the deferred multi-channel-UX work.
    """
    role_list = frozenset({ROLE_OPERATOR})
    tenant_context = TenantContext(
        tenant_id=messaging.webhook_tenant_id,
        jurisdiction=messaging.webhook_jurisdiction,
        cost_attribution_id=messaging.webhook_tenant_id,
    )
    return ActorContext(
        tenant_context=tenant_context,
        actor_id="twilio-webhook",
        role_list=role_list,
        authorisation_set=authorisations_for_roles(role_list),
    )


async def _run_manual_entry_cell(
    *,
    messaging: MessagingComposition,
    audit_port: AuditPort,
    actor: ActorContext,
    inbound_body: str,
    reply_to: str,
    inbound_intake_id: UUID,
) -> None:
    """Run the manual entry cell over an inbound message and reply (S46).

    The cell extracts intent, drives the intake-canonical portfolio
    orchestration, and composes a cited response per D131; the
    rendered reply goes back to the operator as an outbound WhatsApp
    message. ``inbound_intake_id`` is the IntakeRecord that the
    webhook's ``record_intake_and_record_inbound_message`` already
    persisted — the cell uses it as the ``originating_intake_id`` of
    any PendingClarification it creates at Case 2, satisfying the
    `fk_pending_clar_intake_id` FK constraint on intakes(id).
    """
    cell = ManualEntryCell(
        structured_output_port=messaging.structured_output_port,
        portfolio_gateway=messaging.portfolio_gateway,
        actor=actor,
        confidence_calculator=messaging.confidence_calculator,
        threshold_resolver=messaging.threshold_resolver,
        pending_clarification_reader=messaging.pending_clarification_reader,
        pending_clarification_repository=(
            messaging.pending_clarification_repository
        ),
        audit_port=audit_port,
        originating_intake_id=inbound_intake_id,
    )
    state = await cell.open(
        ConversationInvocation(
            purpose="manual_entry", actor_id=actor.actor_id
        )
    )
    state = await cell.turn(state, ConversationInput(text=inbound_body))
    await cell.close(
        state, ConversationClosure(reason="manual_entry handled")
    )
    await send_message(
        repository=messaging.repository,
        delivery_port=messaging.delivery_port,
        audit_port=audit_port,
        channel_resolver=messaging.channel_resolver,
        actor=actor,
        from_address=messaging.from_address,
        to_address=reply_to,
        body=state.payload["response_text"],
    )


async def _load_prior_mirror_focus(
    *,
    messaging: MessagingComposition,
    actor: ActorContext,
) -> Any:
    """Find the most recent mirror-conversation outbound and extract its focus.

    Per D141: each mirror-conversation outbound persists
    ``current_focus_artefact`` into its ``cell_payload`` column. The
    next turn looks at the most recent mirror-conversation outbound
    Message in the tenant's history; if its ``cell_payload`` matches
    the expected mirror shape, the focus extracts via
    ``extract_focus_from_cell_payload``; otherwise None.

    Phase 2-A is single-user single-tenant so a small page-scan covers
    the lookup; Phase 2-B+ may add a dedicated read surface.
    """
    page = await messaging.repository.list_for_tenant(
        tenant_context=actor.tenant_context,
        filters=None,
        cursor=None,
        page_size=_CONVERSATION_HISTORY_WINDOW,
    )
    for message in page.messages:
        if message.direction is not MessageDirection.OUTBOUND:
            continue
        focus = extract_focus_from_cell_payload(message.cell_payload)
        if focus is not None:
            return focus
    return None


async def _run_audit_conversation_cell(
    *,
    messaging: MessagingComposition,
    audit_port: AuditPort,
    actor: ActorContext,
    inbound_body: str,
    reply_to: str,
    inbound_intake_id: UUID,
) -> None:
    """Run the audit-conversation cell over an inbound message and reply (S51).

    Mirrors the manual-entry runner shape but constructs the
    AuditConversationCell with its read-side collaborators (the
    existing S36 AuditEventReader and the apps/-layer
    PortfolioCaseLookup adapter). The audit-conversation
    AuditConversationResponse renders through its own WhatsApp
    renderer at ``contexts/audit_conversation/application/response.py``.
    """
    cell = AuditConversationCell(
        structured_output_port=messaging.structured_output_port,
        audit_event_reader=messaging.audit_event_reader,
        portfolio_case_lookup=messaging.portfolio_case_lookup,
        actor=actor,
        confidence_calculator=messaging.confidence_calculator,
        threshold_resolver=messaging.threshold_resolver,
        pending_clarification_reader=messaging.pending_clarification_reader,
        pending_clarification_repository=(
            messaging.pending_clarification_repository
        ),
        audit_port=audit_port,
        originating_intake_id=inbound_intake_id,
    )
    state = await cell.open(
        ConversationInvocation(
            purpose="audit_query", actor_id=actor.actor_id
        )
    )
    state = await cell.turn(state, ConversationInput(text=inbound_body))
    await cell.close(
        state, ConversationClosure(reason="audit_query handled")
    )

    from datetime import datetime, timezone
    response = state.payload["audit_response"]
    rendered = render_audit_for_whatsapp(
        response, composed_at=datetime.now(timezone.utc)
    )
    await send_message(
        repository=messaging.repository,
        delivery_port=messaging.delivery_port,
        audit_port=audit_port,
        channel_resolver=messaging.channel_resolver,
        actor=actor,
        from_address=messaging.from_address,
        to_address=reply_to,
        body=rendered,
    )


async def _run_mirror_conversation_cell(
    *,
    messaging: MessagingComposition,
    audit_port: AuditPort,
    actor: ActorContext,
    inbound_body: str,
    reply_to: str,
    inbound_intake_id: UUID,
) -> None:
    """Run the mirror-conversation cell over an inbound message and reply (S52).

    Loads the prior focus from the most recent mirror-conversation
    outbound's cell_payload per D141 before constructing the cell, so
    relative intents resolve against the correct anchor. Persists the
    composed response and (per D141) the cell_payload onto the
    outbound Message.
    """
    prior_focus = await _load_prior_mirror_focus(
        messaging=messaging, actor=actor
    )
    cell = MirrorConversationCell(
        structured_output_port=messaging.structured_output_port,
        mirror_portfolio_reader=messaging.mirror_portfolio_reader,
        actor=actor,
        confidence_calculator=messaging.confidence_calculator,
        threshold_resolver=messaging.threshold_resolver,
        pending_clarification_reader=messaging.pending_clarification_reader,
        pending_clarification_repository=(
            messaging.pending_clarification_repository
        ),
        audit_port=audit_port,
        prior_focus=prior_focus,
        originating_intake_id=inbound_intake_id,
    )
    state = await cell.open(
        ConversationInvocation(
            purpose="mirror_query", actor_id=actor.actor_id
        )
    )
    state = await cell.turn(state, ConversationInput(text=inbound_body))
    await cell.close(
        state, ConversationClosure(reason="mirror_query handled")
    )

    from datetime import datetime, timezone

    from contexts.mirror_conversation.application.response import (
        MirrorConversationResponse,
    )
    response: MirrorConversationResponse = state.payload["mirror_response"]
    rendered = render_mirror_for_whatsapp(
        response, composed_at=datetime.now(timezone.utc)
    )
    cell_payload = state.payload.get("cell_payload")
    await send_message(
        repository=messaging.repository,
        delivery_port=messaging.delivery_port,
        audit_port=audit_port,
        channel_resolver=messaging.channel_resolver,
        actor=actor,
        from_address=messaging.from_address,
        to_address=reply_to,
        body=rendered,
        cell_payload=cell_payload,
    )


async def _load_conversation_history(
    *,
    messaging: MessagingComposition,
    actor: ActorContext,
    limit: int = _CONVERSATION_HISTORY_WINDOW,
) -> tuple[ConversationTurn, ...]:
    """Load the recent N messages for the actor's tenant as ConversationTurns.

    Messages are returned newest-first by the repository; the
    classifier reads them oldest-first, so we reverse the slice. Each
    inbound message becomes a ``user`` turn; each outbound an
    ``assistant`` turn.
    """
    page = await messaging.repository.list_for_tenant(
        tenant_context=actor.tenant_context,
        filters=None,
        cursor=None,
        page_size=limit,
    )
    chronological = list(reversed(page.messages))
    turns: list[ConversationTurn] = []
    for message in chronological:
        if not message.body or not message.body.strip():
            continue
        role = (
            "user"
            if message.direction is MessageDirection.INBOUND
            else "assistant"
        )
        turns.append(ConversationTurn(role=role, text=message.body))
    return tuple(turns)


async def _resolve_calendar_connection_id(
    *, session_factory, tenant_id: str
) -> UUID | None:
    """Resolve the tenant's google-calendar connection id, or None.

    Composition-root lookup: the calendar runner needs the connection id
    to wire the refresh adapter, and ConnectionRepository.get_connection
    is by-id only. A small select on the connections table is the seam.
    """
    stmt = sa.select(calendar_connections_table.c.id).where(
        calendar_connections_table.c.tenant_id == tenant_id,
        calendar_connections_table.c.provider_config_key == "google-calendar",
    )
    async with session_factory() as session:
        result = await session.execute(stmt)
        row = result.first()
    return UUID(str(row[0])) if row is not None else None


async def _run_calendar_conversation_cell(
    *,
    messaging: MessagingComposition,
    audit_port: AuditPort,
    actor: ActorContext,
    inbound_body: str,
    reply_to: str,
    inbound_intake_id: UUID,
) -> None:
    """Run the calendar-conversation cell over an inbound message and reply (S55b-2).

    Mirrors the audit/mirror runners: reuses the messaging composition's
    shared ports (structured-output, confidence, threshold, pending) and
    builds the calendar-specific collaborators per request — the Meeting
    store (reader) and the D150 refresh adapter wired to the real Nango
    Proxy + embedder + graph (the consumer landed at S55b-1). When no
    calendar connection exists for the tenant, the cell runs without a
    refresh port and answers from the cached store.
    """
    tenant_id = str(actor.tenant_context.tenant_id)
    wiring = build_tenant_wiring(tenant_id)
    session_factory = wiring.session_factory

    async def _resolver(_tid):
        return session_factory

    bound = TenantId(str(actor.tenant_context.tenant_id))
    meeting_store = PostgresMeetingStore(
        per_tenant_sessionmaker_resolver=_resolver, bound_tenant_id=bound
    )
    connection_id = await _resolve_calendar_connection_id(
        session_factory=session_factory, tenant_id=tenant_id
    )
    refresh_port = (
        build_calendar_refresh_adapter(
            tenant_id=tenant_id, connection_id=connection_id
        )
        if connection_id is not None
        else None
    )

    cell = CalendarConversationCell(
        structured_output_port=messaging.structured_output_port,
        meeting_reader=meeting_store,
        actor=actor,
        confidence_calculator=messaging.confidence_calculator,
        threshold_resolver=messaging.threshold_resolver,
        pending_clarification_reader=messaging.pending_clarification_reader,
        pending_clarification_repository=(
            messaging.pending_clarification_repository
        ),
        audit_port=audit_port,
        refresh_port=refresh_port,
        originating_intake_id=inbound_intake_id,
    )
    state = await cell.open(
        ConversationInvocation(
            purpose="calendar_query", actor_id=actor.actor_id
        )
    )
    state = await cell.turn(state, ConversationInput(text=inbound_body))
    await cell.close(
        state, ConversationClosure(reason="calendar_query handled")
    )

    from datetime import datetime, timezone

    response = state.payload["calendar_response"]
    rendered = render_calendar_for_whatsapp(
        response, composed_at=datetime.now(timezone.utc)
    )
    await send_message(
        repository=messaging.repository,
        delivery_port=messaging.delivery_port,
        audit_port=audit_port,
        channel_resolver=messaging.channel_resolver,
        actor=actor,
        from_address=messaging.from_address,
        to_address=reply_to,
        body=rendered,
    )


def _build_cell_runners(
    *,
    messaging: MessagingComposition,
    audit_port: AuditPort,
    actor: ActorContext,
    reply_to: str,
) -> dict:
    """Build the per-cell runners the dispatch_inbound use case selects from."""

    async def _manual_entry_runner(context: DispatchContext) -> None:
        await _run_manual_entry_cell(
            messaging=messaging,
            audit_port=audit_port,
            actor=actor,
            inbound_body=context.inbound_text,
            reply_to=reply_to,
            inbound_intake_id=context.inbound_intake_id,
        )

    async def _audit_runner(context: DispatchContext) -> None:
        await _run_audit_conversation_cell(
            messaging=messaging,
            audit_port=audit_port,
            actor=actor,
            inbound_body=context.inbound_text,
            reply_to=reply_to,
            inbound_intake_id=context.inbound_intake_id,
        )

    async def _mirror_runner(context: DispatchContext) -> None:
        await _run_mirror_conversation_cell(
            messaging=messaging,
            audit_port=audit_port,
            actor=actor,
            inbound_body=context.inbound_text,
            reply_to=reply_to,
            inbound_intake_id=context.inbound_intake_id,
        )

    async def _calendar_runner(context: DispatchContext) -> None:
        await _run_calendar_conversation_cell(
            messaging=messaging,
            audit_port=audit_port,
            actor=actor,
            inbound_body=context.inbound_text,
            reply_to=reply_to,
            inbound_intake_id=context.inbound_intake_id,
        )

    return {
        CellIdentifier.MANUAL_ENTRY: _manual_entry_runner,
        CellIdentifier.AUDIT_CONVERSATION: _audit_runner,
        CellIdentifier.MIRROR_CONVERSATION: _mirror_runner,
        CellIdentifier.CALENDAR_CONVERSATION: _calendar_runner,
    }


@router.post("/send", response_model=MessageResponse, status_code=201)
async def send_message_route(
    body: SendMessageRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    messaging: Annotated[
        MessagingComposition, Depends(get_messaging_composition)
    ],
    audit_port: Annotated[AuditPort, Depends(get_audit_port)],
) -> MessageResponse:
    """Send an outbound WhatsApp message."""
    try:
        message = await send_message(
            repository=messaging.repository,
            delivery_port=messaging.delivery_port,
            audit_port=audit_port,
            channel_resolver=messaging.channel_resolver,
            actor=actor,
            from_address=messaging.from_address,
            to_address=body.to_address,
            body=body.body,
        )
    except ValueError as exc:
        if "tenant" in str(exc):
            raise BoundTenantIdMismatchError(exc) from exc
        raise
    return message_to_response(message)


@router.post("/inbound", response_model=InboundWebhookAck, status_code=200)
async def inbound_webhook_route(
    request: Request,
    messaging: Annotated[
        MessagingComposition, Depends(get_messaging_composition)
    ],
    intake_repository: Annotated[
        IntakeRepository, Depends(get_intake_repository)
    ],
    audit_port: Annotated[AuditPort, Depends(get_audit_port)],
) -> InboundWebhookAck:
    """Receive an inbound Twilio WhatsApp message.

    Verifies the ``X-Twilio-Signature`` over the form payload before
    processing; a failed check raises ``WebhookSignatureError`` (403).
    The verified payload drives the intake-canonical orchestration —
    an IntakeRecord plus an inbound Message.
    """
    # Imported here so the route module stays free of the twilio SDK
    # at import time; the verification helper is twilio-confined.
    from contexts.messaging.adapters.outbound.twilio.twilio_message_delivery import (  # noqa: E501
        strip_channel_prefix,
        verify_twilio_signature,
    )

    # Twilio posts application/x-www-form-urlencoded; parse the raw
    # body directly (no python-multipart dependency) so the signature
    # is computed over exactly the delivered parameters.
    raw = await request.body()
    params = dict(urllib.parse.parse_qsl(raw.decode("utf-8")))
    signature = request.headers.get("X-Twilio-Signature", "")
    url = messaging.webhook_url or str(request.url)
    if not verify_twilio_signature(
        auth_token=messaging.twilio_auth_token,
        url=url,
        params=params,
        signature=signature,
    ):
        raise WebhookSignatureError()

    actor = _synthesise_webhook_actor(messaging)
    inbound_body = params.get("Body", "")
    result = await record_intake_and_record_inbound_message(
        intake_repository=intake_repository,
        audit_port=audit_port,
        message_writer=messaging.message_writer,
        actor=actor,
        channel=MessageChannel.WHATSAPP.value,
        from_address=strip_channel_prefix(params.get("From", "")),
        to_address=strip_channel_prefix(params.get("To", "")),
        body=inbound_body,
        external_id=params.get("MessageSid") or None,
    )

    # S52 (D140): the inbound dispatches through the meta-classifier
    # routing substrate. The dispatch_inbound use case picks between
    # active-pending routing (Step 2 of the dispatch flow) and meta-
    # classification (Steps 3-5). The dispatched cell runs via the
    # CellDispatch port (D133); the webhook returns 2xx promptly while
    # the dispatch and the cell run complete asynchronously. The
    # inbound Message and its IntakeRecord are already persisted above
    # as the canonical record-of-arrival; dispatch failure never
    # erases that.
    reply_to = strip_channel_prefix(params.get("From", ""))
    history = await _load_conversation_history(
        messaging=messaging, actor=actor
    )
    cell_runners = _build_cell_runners(
        messaging=messaging,
        audit_port=audit_port,
        actor=actor,
        reply_to=reply_to,
    )
    dispatch_context = DispatchContext(
        tenant_id=UUID(actor.tenant_context.tenant_id),
        user_id=actor.actor_id,
        inbound_text=inbound_body,
        inbound_intake_id=result.intake_id,
        reply_to=reply_to,
        conversation_history=history,
    )
    await dispatch_inbound.execute(
        context=dispatch_context,
        actor=actor,
        pending_reader=messaging.pending_clarification_reader,
        pending_repository=messaging.pending_clarification_repository,
        meta_classifier=messaging.meta_classifier,
        high_confidence_threshold=messaging.high_confidence_threshold,
        cell_dispatch=messaging.cell_dispatch,
        audit_port=audit_port,
        cell_runners=cell_runners,
        message_repository=messaging.repository,
        delivery_port=messaging.delivery_port,
        channel_resolver=messaging.channel_resolver,
        from_address=messaging.from_address,
    )

    return webhook_ack(result)


@router.get("/messages/{message_id}", response_model=MessageResponse)
async def get_message_route(
    message_id: UUID,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    messaging: Annotated[
        MessagingComposition, Depends(get_messaging_composition)
    ],
) -> MessageResponse:
    """Return the Message, or 404 when absent for the tenant."""
    try:
        message = await get_message(
            repository=messaging.repository,
            actor=actor,
            message_id=message_id,
        )
    except ValueError as exc:
        if "tenant" in str(exc):
            raise BoundTenantIdMismatchError(exc) from exc
        raise
    if message is None:
        raise MessageNotFoundError(str(message_id))
    return message_to_response(message)


@router.get("/messages", response_model=MessageListResponse)
async def list_messages_route(
    parsed: Annotated[
        tuple[MessageListFilters, MessageListCursor | None, int],
        Depends(parse_message_list_query),
    ],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    messaging: Annotated[
        MessagingComposition, Depends(get_messaging_composition)
    ],
) -> MessageListResponse:
    """List the authenticated tenant's messages, newest first, paginated."""
    filters, cursor, page_size = parsed
    try:
        page = await list_messages(
            repository=messaging.repository,
            actor=actor,
            filters=filters,
            cursor=cursor,
            page_size=page_size,
        )
    except ValueError as exc:
        if "tenant" in str(exc):
            raise BoundTenantIdMismatchError(exc) from exc
        raise
    next_cursor = (
        encode_message_cursor(page.next_cursor)
        if page.next_cursor is not None
        else None
    )
    return message_list_to_response(page, next_cursor)
