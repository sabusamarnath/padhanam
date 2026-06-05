"""HTTP routes for the live conversational-turn-over-HTTP surface (D158, S59).

The daily driver's open-into-cell becomes a live conversation: opening a
Case runs the existing portfolio mirror-conversation cell's ``open`` then
``turn`` and renders the cell's recommendation-shaped reply plus its
resolved citations; further turns advance the same cell.

- ``POST /api/v1/daily-driver/conversation/open`` — open on a focus Case;
  returns the opening assistant turn + the threaded ``ConversationState``.
- ``POST /api/v1/daily-driver/conversation/turn`` — advance one input;
  returns the next ``ConversationState`` + the cell's reply + citations.

Both routes resolve a request-scoped ``ActorContext`` via
``get_actor_context`` (bearer Principal + tenant registry), so tenant +
jurisdiction isolation (D12) holds: a turn runs only against the actor's
own tenant. The web adapter is stateless per turn (D115) — the cell's
collaborators come from the shared ``MessagingComposition`` and the
drill-down focus threads through the client, not a server-side thread.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from apps.api._conversation_cell_wiring import (
    _CALENDAR_PURPOSE,
    FOCUS_KIND_CALENDAR,
    FOCUS_KIND_CASE,
    advance_calendar_conversation,
    advance_conversation,
    open_calendar_conversation,
    open_conversation,
)
from apps.api._messaging_wiring import MessagingComposition
from apps.api.middleware import get_actor_context
from apps.api.routers._conversation_dto import (
    ConversationTurnDTO,
    OpenConversationRequest,
    TurnRequest,
    result_to_dto,
)
from apps.api.routers.messaging import get_audit_port, get_messaging_composition
from contexts.audit.domain.ports import AuditPort
from shared_kernel import ActorContext

router = APIRouter(
    prefix="/api/v1/daily-driver/conversation", tags=["daily-driver-conversation"]
)


@router.post("/open", response_model=ConversationTurnDTO)
async def open_conversation_route(
    body: OpenConversationRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    messaging: Annotated[
        MessagingComposition, Depends(get_messaging_composition)
    ],
    audit_port: Annotated[AuditPort, Depends(get_audit_port)],
) -> ConversationTurnDTO:
    """Open a live conversation on a focus Case or calendar item (D158, D159)."""
    if body.focus_kind == FOCUS_KIND_CASE:
        result = await open_conversation(
            messaging=messaging,
            audit_port=audit_port,
            actor=actor,
            focus_id=body.focus_id,
        )
        not_found = "case not found"
    elif body.focus_kind == FOCUS_KIND_CALENDAR:
        result = await open_calendar_conversation(
            messaging=messaging,
            audit_port=audit_port,
            actor=actor,
            focus_id=body.focus_id,
        )
        not_found = "meeting not found"
    else:
        # Phase 2-A wires the Case and calendar cells; a Commitment-focus
        # cell is named out (D158) until dogfooding shows one is needed.
        raise HTTPException(
            status_code=422,
            detail=(
                f"unsupported focus_kind {body.focus_kind!r}; "
                "expected CASE or CALENDAR"
            ),
        )
    if result is None:
        raise HTTPException(status_code=404, detail=not_found)
    return result_to_dto(result)


@router.post("/turn", response_model=ConversationTurnDTO)
async def turn_route(
    body: TurnRequest,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    messaging: Annotated[
        MessagingComposition, Depends(get_messaging_composition)
    ],
    audit_port: Annotated[AuditPort, Depends(get_audit_port)],
) -> ConversationTurnDTO:
    """Advance a live conversation by one operator turn.

    Dispatch is by the client-threaded ``purpose``: a ``calendar_query``
    advances the calendar cell, anything else the mirror cell — the same
    stateless path, two implementers (D159).
    """
    if body.state.purpose == _CALENDAR_PURPOSE:
        result = await advance_calendar_conversation(
            messaging=messaging,
            audit_port=audit_port,
            actor=actor,
            conversation_id=body.state.conversation_id,
            purpose=body.state.purpose,
            turn_count=body.state.turn_count,
            text=body.text,
        )
    else:
        result = await advance_conversation(
            messaging=messaging,
            audit_port=audit_port,
            actor=actor,
            conversation_id=body.state.conversation_id,
            purpose=body.state.purpose,
            turn_count=body.state.turn_count,
            cell_payload=body.state.cell_payload,
            text=body.text,
        )
    return result_to_dto(result)


__all__ = ["router"]
