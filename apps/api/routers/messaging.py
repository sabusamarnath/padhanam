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
from contexts.intake.application.record_intake_and_record_inbound_message import (  # noqa: E501
    record_intake_and_record_inbound_message,
)
from contexts.intake.ports.intake_repository import IntakeRepository
from contexts.messaging.application.cursor import encode_message_cursor
from contexts.messaging.application.get_message import get_message
from contexts.messaging.application.list_messages import list_messages
from contexts.messaging.application.manual_entry_cell import ManualEntryCell
from contexts.messaging.application.send_message import send_message
from contexts.messaging.domain import MessageChannel
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
)
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles

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
) -> None:
    """Run the manual entry cell over an inbound message and reply (S46).

    The cell extracts intent, drives the intake-canonical portfolio
    orchestration, and composes a cited response per D131; the
    rendered reply goes back to the operator as an outbound WhatsApp
    message.
    """
    cell = ManualEntryCell(
        structured_output_port=messaging.structured_output_port,
        portfolio_gateway=messaging.portfolio_gateway,
        actor=actor,
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
        actor=actor,
        from_address=messaging.from_address,
        to_address=reply_to,
        body=state.payload["response_text"],
    )


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

    # S47 (D133): the cell run dispatches to a background task via the
    # CellDispatch port — the webhook returns 2xx promptly while the
    # cell completes asynchronously. The dispatch port's contract
    # captures and logs any exception raised by the cell, closing the
    # bare-``except`` gap from the prior synchronous shape (S46 smoke
    # finding). The inbound Message and its IntakeRecord are already
    # persisted above as the canonical record-of-arrival; cell failure
    # never erases that.
    reply_to = strip_channel_prefix(params.get("From", ""))
    await messaging.cell_dispatch.dispatch(
        lambda: _run_manual_entry_cell(
            messaging=messaging,
            audit_port=audit_port,
            actor=actor,
            inbound_body=inbound_body,
            reply_to=reply_to,
        ),
        context={
            "intake_id": str(result.intake_id),
            "tenant_id": str(actor.tenant_context.tenant_id),
            "external_id": params.get("MessageSid") or None,
        },
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
