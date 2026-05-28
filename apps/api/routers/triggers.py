"""HTTP trigger endpoint for platform-initiated broadcasts (D145, D147, S54).

One route: ``POST /api/v1/internal/triggers/fire``. The deployment's
external scheduler (cron, systemd timer, Kubernetes CronJob) hits the
endpoint to fire a DAILY_SCHEDULED (or, at S57, THRESHOLD_CROSSED)
trigger. The route bypasses the bearer-auth middleware (its path is in
the middleware's public-path set) and authenticates via the
``X-Internal-Secret`` header validated against
``MessagingSettings.internal_secret``.

The handler validates the secret, synthesises an operator ActorContext
for the configured broadcast tenant (the scheduler carries no per-user
Principal), constructs the TriggerContext, and delegates to the
FireTrigger use case (D147 seven-step flow). A fresh fire returns 200
with status ACCEPTED; a duplicate within the idempotency window returns
200 with status ALREADY_FIRED (no audit-chain or dispatch side effects).

DTOs co-locate here per the flat-module router convention. Request
parsing maps the trigger_type string to BroadcastTriggerType; an
unknown value raises a 422 via Pydantic's enum validation.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from apps.api._internal_secret import (
    _INTERNAL_SECRET_HEADER,
    verify_internal_secret,
)
from apps.api._messaging_wiring import MessagingComposition
from contexts.audit.domain.ports import AuditPort
from contexts.messaging.application.fire_trigger import (
    FireTriggerResult,
    fire_trigger,
)
from contexts.messaging.domain.idempotency import resolve_idempotency_key  # noqa: F401
from padhanam.config import MessagingSettings
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles
from shared_kernel.broadcast_flow import BroadcastTriggerType, TriggerContext

router = APIRouter(prefix="/api/v1/internal/triggers", tags=["triggers"])


class FireTriggerRequest(BaseModel):
    """Body for POST /api/v1/internal/triggers/fire.

    ``trigger_type`` is one of the BroadcastTriggerType values;
    ``trigger_id`` is the platform-assigned identifier for chain
    traversability (the BROADCAST_INITIATED audit event references
    it); ``triggered_at`` is the ISO timestamp of trigger entry;
    ``metadata`` is the open per-type slot (empty for DAILY_SCHEDULED;
    optional caller_note for MANUAL). ``user_id`` defaults to the
    configured broadcast operator when omitted (Phase 2-A single
    operator).
    """

    trigger_type: BroadcastTriggerType
    trigger_id: str = Field(min_length=1)
    triggered_at: str = Field(min_length=1)
    user_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class FireTriggerResponse(BaseModel):
    """Wire shape of a FireTrigger outcome."""

    trigger_id: str
    status: str


def get_messaging_composition(request: Request) -> MessagingComposition:
    messaging: MessagingComposition | None = getattr(
        request.app.state, "messaging", None
    )
    if messaging is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=503,
            detail="messaging composition not configured on this API instance",
        )
    return messaging


def get_audit_port(request: Request) -> AuditPort:
    audit_port: AuditPort | None = getattr(request.app.state, "audit_port", None)
    if audit_port is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=503,
            detail="audit port not configured on this API instance",
        )
    return audit_port


def _synthesise_broadcast_actor(
    messaging: MessagingComposition, *, user_id: str
) -> ActorContext:
    """Synthesise an operator ActorContext for the broadcast tenant.

    The internal trigger endpoint carries no per-user Principal; the
    deployment's scheduler fires on the operator's behalf. The actor
    is the operator-role ActorContext for the configured broadcast
    (webhook) tenant — mirroring the inbound webhook's actor
    synthesis. Multi-tenant broadcast routing is the deferred
    multi-channel-UX work.
    """
    role_list = frozenset({ROLE_OPERATOR})
    tenant_context = TenantContext(
        tenant_id=messaging.webhook_tenant_id,
        jurisdiction=messaging.webhook_jurisdiction,
        cost_attribution_id=messaging.webhook_tenant_id,
    )
    return ActorContext(
        tenant_context=tenant_context,
        actor_id=user_id,
        role_list=role_list,
        authorisation_set=authorisations_for_roles(role_list),
    )


@router.post("/fire", response_model=FireTriggerResponse, status_code=200)
async def fire_trigger_route(
    body: FireTriggerRequest,
    request: Request,
    messaging: Annotated[
        MessagingComposition, Depends(get_messaging_composition)
    ],
    audit_port: Annotated[AuditPort, Depends(get_audit_port)],
) -> FireTriggerResponse:
    """Fire a platform-initiated broadcast trigger (D145, D147).

    Authenticates the X-Internal-Secret header, then delegates to the
    FireTrigger use case (D147 seven-step idempotency-then-dispatch
    flow). Returns 200 with ACCEPTED (fresh fire) or ALREADY_FIRED
    (duplicate within the idempotency window).
    """
    settings = MessagingSettings()
    verify_internal_secret(
        presented=request.headers.get(_INTERNAL_SECRET_HEADER),
        configured=settings.internal_secret,
    )

    user_id = body.user_id or messaging.webhook_tenant_id
    actor = _synthesise_broadcast_actor(messaging, user_id=user_id)
    trigger_context = TriggerContext(
        trigger_type=body.trigger_type,
        trigger_id=_coerce_uuid(body.trigger_id),
        triggered_at=body.triggered_at,
        metadata=dict(body.metadata),
    )

    result: FireTriggerResult = await fire_trigger(
        fired_triggers_repository=messaging.fired_triggers_repository,
        audit_port=audit_port,
        broadcast_dispatch=messaging.broadcast_dispatch,
        actor=actor,
        trigger_context=trigger_context,
        operator_timezone=settings.operator_timezone,
    )
    return FireTriggerResponse(
        trigger_id=result.trigger_id, status=result.status.value
    )


def _coerce_uuid(raw: str):
    """Coerce the trigger_id string into a UUID, minting one if malformed.

    The scheduler is expected to supply a UUID; a malformed value
    mints a fresh one so the audit-chain reference is always a valid
    UUID. The minted-vs-supplied distinction is not load-bearing —
    the trigger_id's role is chain traversability, not external
    correlation.
    """
    from uuid import UUID, uuid4

    try:
        return UUID(raw)
    except (ValueError, AttributeError):
        return uuid4()


__all__ = ["FireTriggerRequest", "FireTriggerResponse", "router"]
