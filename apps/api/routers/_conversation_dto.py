"""Request/response DTOs for the live conversation surface (D158, S59).

The web adapter is stateless per turn (D115): ``ConversationStateDTO`` is
the slim state the client threads back on each turn. It carries only the
cell continuity fields plus ``cell_payload`` (the D141 drill-down focus) —
never the full cell response payload, which holds non-serialisable
domain value objects.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from apps.api._conversation_cell_wiring import (
    ConversationTurnResult,
    FOCUS_KIND_CASE,
)


class ConversationStateDTO(BaseModel):
    """The slim, client-threaded conversation state (stateless-per-turn)."""

    conversation_id: str
    purpose: str
    turn_count: int
    is_open: bool
    cell_payload: dict | None = None


class CitationDTO(BaseModel):
    """A source-typed citation chip: human label + non-identifying ref."""

    type: str
    label: str
    ref: str


class ConversationTurnDTO(BaseModel):
    """One conversation turn: the next state, the reply, and its citations."""

    state: ConversationStateDTO
    reply: str
    citations: list[CitationDTO] = Field(default_factory=list)


class OpenConversationRequest(BaseModel):
    """Open a conversation on a focus item. Phase 2-A focus kind is CASE."""

    focus_kind: str = FOCUS_KIND_CASE
    focus_id: UUID


class TurnRequest(BaseModel):
    """Advance a conversation by one turn from the client-threaded state."""

    state: ConversationStateDTO
    text: str


def result_to_dto(result: ConversationTurnResult) -> ConversationTurnDTO:
    """Map a wiring-layer turn result to the HTTP DTO."""
    return ConversationTurnDTO(
        state=ConversationStateDTO(
            conversation_id=result.conversation_id,
            purpose=result.purpose,
            turn_count=result.turn_count,
            is_open=result.is_open,
            cell_payload=result.cell_payload,
        ),
        reply=result.reply,
        citations=[
            CitationDTO(type=c.type, label=c.label, ref=c.ref)
            for c in result.citations
        ],
    )


__all__ = [
    "CitationDTO",
    "ConversationStateDTO",
    "ConversationTurnDTO",
    "OpenConversationRequest",
    "TurnRequest",
    "result_to_dto",
]
