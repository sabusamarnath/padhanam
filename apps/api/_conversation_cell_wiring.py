"""Composition wiring for the live conversational-turn-over-HTTP surface (D158, S59).

The stateless web ConversationFlow adapter. It constructs the existing
portfolio ``MirrorConversationCell`` exactly the way the messaging
dispatch (``apps/api/routers/messaging.py:_run_mirror_conversation_cell``)
does — from the shared ``MessagingComposition`` collaborators plus a
request-scoped ``ActorContext`` — runs the cell's ``open`` then ``turn``,
and maps the cell's response to a JSON-friendly turn result.

Stateless per turn (D115): the conversation does not persist server-side.
The drill-down focus (the D141 ``cell_payload``) threads through the
*client* across turns — the turn result carries the serialised focus, the
next turn request returns it, and this module reconstructs ``prior_focus``
from it via ``extract_focus_from_cell_payload``. No ``messages`` row, no
migration. The cell's own ``PendingClarification`` (medium-confidence and
resolution-ambiguity paths) is reused unchanged — the cell's existing
user-scoped mechanism (D134), not a parallel state machine this adapter
introduces; the adapter itself holds no conversation state.

Citation IDs from the cell's ``MirrorConversationResponse`` resolve to
source-typed human labels through the same ``mirror_portfolio_reader`` the
cell reads from — no raw UUID reaches the surface (D131/D138 first web
instance). ``cited_audit_events`` stays empty per the mirror disposition
(D138); the resolver carries the field defensively for future implementers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from apps.api._messaging_wiring import MessagingComposition
from contexts.audit.domain.ports import AuditPort
from contexts.calendar.ports.meeting_repository import MeetingReader
from contexts.calendar_conversation.application.cell import (
    CalendarConversationCell,
)
from contexts.calendar_conversation.application.response import (
    CalendarConversationResponse,
)
from contexts.mirror_conversation.application.cell import (
    MirrorConversationCell,
)
from contexts.mirror_conversation.application.response import (
    MirrorConversationResponse,
    extract_focus_from_cell_payload,
)
from shared_kernel import (
    ActorContext,
    ConversationInput,
    ConversationInvocation,
    ConversationState,
)
from shared_kernel.conversation_flow import ArtefactCitation

# The mirror-conversation cell answers a portfolio Case; the S59 surface
# opens a Case into that cell. The S60 surface (D159) also opens a calendar
# item into the calendar-conversation cell over the *same* stateless path —
# a second implementer, not a parallel state machine. The focus kinds the
# surface accepts, and the purposes the two cells thread.
FOCUS_KIND_CASE = "CASE"
FOCUS_KIND_CALENDAR = "CALENDAR"

_PURPOSE = "mirror_query"
_CALENDAR_PURPOSE = "calendar_query"


@dataclass(frozen=True)
class ResolvedCitation:
    """A citation resolved from an id to a source-typed human label (D131).

    ``ref`` is a short-hex prefix of the artefact id for a compact,
    non-identifying reference — never the raw UUID (the surface renders
    ``type`` and ``label``; ``ref`` is a stable short handle).
    """

    type: str
    label: str
    ref: str


@dataclass(frozen=True)
class ConversationTurnResult:
    """The stateless result of one web conversation turn.

    Carries the slim ``ConversationState`` the client threads back on the
    next turn (``conversation_id``/``purpose``/``turn_count``/``is_open``
    plus ``cell_payload`` — the D141 drill-down focus), the cell's reply
    text, and the resolved citation chips.
    """

    conversation_id: str
    purpose: str
    turn_count: int
    is_open: bool
    cell_payload: dict | None
    reply: str
    citations: list[ResolvedCitation] = field(default_factory=list)


def _short_hex(identifier: UUID) -> str:
    """Short-hex prefix of a UUID for a compact, non-identifying ref."""
    return identifier.hex[:8]


def build_mirror_cell(
    *,
    messaging: MessagingComposition,
    audit_port: AuditPort,
    actor: ActorContext,
    prior_focus: ArtefactCitation | None,
) -> MirrorConversationCell:
    """Construct the mirror-conversation cell, mirroring the messaging dispatch.

    Same collaborators as ``_run_mirror_conversation_cell``; the only web
    difference is ``prior_focus`` arrives from the client-threaded
    ``cell_payload`` rather than from the prior outbound message's column.
    """
    return MirrorConversationCell(
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
        originating_channel="WEB",
    )


async def _resolve_citations(
    *,
    reader,
    actor: ActorContext,
    response: MirrorConversationResponse,
) -> list[ResolvedCitation]:
    """Resolve the response's citation tuples to source-typed labels (D131).

    Resolution reads through the same ``mirror_portfolio_reader`` the cell
    uses, so there is no second read path. A citation whose artefact can no
    longer load falls back to a short-hex label rather than leaking a raw
    id or dropping the chip.
    """
    resolved: list[ResolvedCitation] = []

    for citation in response.cited_artefacts:
        ref = _short_hex(citation.artefact_id)
        if citation.artefact_type == "case":
            detail = await reader.get_case_detail(
                actor=actor, case_id=citation.artefact_id
            )
            label = detail.case.title if detail is not None else f"case {ref}"
            resolved.append(
                ResolvedCitation(type="case", label=label, ref=ref)
            )
        elif citation.artefact_type == "data_point":
            data_point = await reader.get_data_point(
                actor=actor, data_point_id=citation.artefact_id
            )
            label = (
                _data_point_label(data_point.current_value)
                if data_point is not None
                else f"data point {ref}"
            )
            resolved.append(
                ResolvedCitation(type="data point", label=label, ref=ref)
            )
        else:
            # Unknown discriminator: surface type + short ref, never the
            # raw id. (The validated union keeps this branch unreachable
            # today; it is defensive against future artefact types.)
            resolved.append(
                ResolvedCitation(
                    type=citation.artefact_type, label=ref, ref=ref
                )
            )

    # Intake / audit citations carry no label source in the mirror reader;
    # mirror leaves both tuples empty (D138). Render them by short ref if a
    # future implementer populates them, keeping the no-raw-UUID guarantee.
    for intake_id in response.cited_intake_records:
        ref = _short_hex(intake_id)
        resolved.append(ResolvedCitation(type="intake", label=ref, ref=ref))
    for audit_id in response.cited_audit_events:
        ref = _short_hex(audit_id)
        resolved.append(ResolvedCitation(type="audit", label=ref, ref=ref))

    return resolved


def _data_point_label(value: dict) -> str:
    """Human label for a DataPoint from its current value (mirror convention)."""
    text = value.get("text")
    if isinstance(text, str) and text.strip():
        return text
    joined = " ".join(str(v) for v in value.values() if isinstance(v, str))
    return joined or "data point"


async def _result_from_state(
    *,
    reader,
    actor: ActorContext,
    state: ConversationState,
) -> ConversationTurnResult:
    """Map a cell ``ConversationState`` to the stateless web turn result."""
    response: MirrorConversationResponse = state.payload["mirror_response"]
    citations = await _resolve_citations(
        reader=reader, actor=actor, response=response
    )
    return ConversationTurnResult(
        conversation_id=state.conversation_id,
        purpose=state.purpose,
        turn_count=state.turn_count,
        is_open=state.is_open,
        cell_payload=state.payload.get("cell_payload"),
        reply=response.text,
        citations=citations,
    )


async def open_conversation(
    *,
    messaging: MessagingComposition,
    audit_port: AuditPort,
    actor: ActorContext,
    focus_id: UUID,
) -> ConversationTurnResult | None:
    """Open a conversation on a focus Case: run the cell's open then turn.

    Returns ``None`` when the focus Case does not exist for the actor (the
    router maps that to 404). The opening turn is the cell's real
    resolution path on ``"show me {title}"`` (REAL_TIME_REQUIRED, D122),
    which grounds on the clicked Case at dogfooding scale.
    """
    reader = messaging.mirror_portfolio_reader
    detail = await reader.get_case_detail(actor=actor, case_id=focus_id)
    if detail is None:
        return None

    cell = build_mirror_cell(
        messaging=messaging,
        audit_port=audit_port,
        actor=actor,
        prior_focus=None,
    )
    state = await cell.open(
        ConversationInvocation(purpose=_PURPOSE, actor_id=actor.actor_id)
    )
    state = await cell.turn(
        state, ConversationInput(text=f"show me {detail.case.title}")
    )
    return await _result_from_state(reader=reader, actor=actor, state=state)


async def advance_conversation(
    *,
    messaging: MessagingComposition,
    audit_port: AuditPort,
    actor: ActorContext,
    conversation_id: str,
    purpose: str,
    turn_count: int,
    cell_payload: dict | None,
    text: str,
) -> ConversationTurnResult:
    """Advance a conversation by one turn from the client-threaded state.

    The drill-down focus is reconstructed from the client's ``cell_payload``
    (D141, threaded not persisted); the incoming ``ConversationState``
    carries only the continuity fields the cell's ``turn`` needs.
    """
    reader = messaging.mirror_portfolio_reader
    prior_focus = extract_focus_from_cell_payload(cell_payload)
    cell = build_mirror_cell(
        messaging=messaging,
        audit_port=audit_port,
        actor=actor,
        prior_focus=prior_focus,
    )
    state_in = ConversationState(
        conversation_id=conversation_id,
        purpose=purpose or _PURPOSE,
        turn_count=turn_count,
        is_open=True,
        payload={},
    )
    state = await cell.turn(state_in, ConversationInput(text=text))
    return await _result_from_state(reader=reader, actor=actor, state=state)


# ===================================================================
# Calendar conversation — the second implementer on the same path (D159)
# ===================================================================
#
# A calendar item opens into the existing `calendar_conversation` cell
# (S55b), reached through the same stateless open/turn shape as the mirror
# cell. The differences are local and named: a different cell construction
# (the Meeting store + the D150 refresh port), a different response payload
# key (`calendar_response`), and `meeting`-typed citations. The cell holds
# its own `PendingClarification` (D134/D139) exactly as the mirror cell
# does; this adapter holds no conversation state, and the calendar cell
# does not drill down, so `cell_payload` stays empty for calendar turns.


def _build_calendar_collaborators(
    actor: ActorContext,
) -> tuple[MeetingReader, object | None]:
    """Build the per-request Meeting store + optional refresh port (D150).

    Mirrors ``messaging.py:_run_calendar_conversation_cell``: a Meeting
    store bound to the request's tenant, plus the refresh adapter wired to
    the real Nango Proxy when a google-calendar connection exists for the
    tenant. When no calendar is connected the cell answers from the cached
    store with no refresh (and the live smoke is operator-gated, AC8).
    """
    import sqlalchemy as sa

    from apps.cli._runtime import build_tenant_wiring
    from contexts.calendar.adapters.outbound.postgres._tables import (
        connections as calendar_connections_table,
    )
    from contexts.calendar.adapters.outbound.postgres.meeting_store import (
        PostgresMeetingStore,
    )
    from shared_kernel import TenantId

    tenant_id = str(actor.tenant_context.tenant_id)
    wiring = build_tenant_wiring(tenant_id)
    session_factory = wiring.session_factory

    async def _resolver(_tid):
        return session_factory

    bound = TenantId(tenant_id)
    meeting_store = PostgresMeetingStore(
        per_tenant_sessionmaker_resolver=_resolver, bound_tenant_id=bound
    )

    async def _resolve_connection_id() -> UUID | None:
        stmt = sa.select(calendar_connections_table.c.id).where(
            calendar_connections_table.c.tenant_id == tenant_id,
            calendar_connections_table.c.provider_config_key
            == "google-calendar",
        )
        async with session_factory() as session:
            result = await session.execute(stmt)
            row = result.first()
        return UUID(str(row[0])) if row is not None else None

    return meeting_store, _resolve_connection_id


def build_calendar_cell(
    *,
    messaging: MessagingComposition,
    audit_port: AuditPort,
    actor: ActorContext,
    meeting_reader: MeetingReader,
    refresh_port: object | None,
) -> CalendarConversationCell:
    """Construct the calendar-conversation cell, mirroring the messaging dispatch.

    Same shared collaborators as ``_run_calendar_conversation_cell``
    (structured-output, confidence, threshold, pending, audit); the
    calendar-specific collaborators are the Meeting reader and the D150
    refresh port. The originating channel is ``WEB`` (the S59 convention).
    """
    return CalendarConversationCell(
        structured_output_port=messaging.structured_output_port,
        meeting_reader=meeting_reader,
        actor=actor,
        confidence_calculator=messaging.confidence_calculator,
        threshold_resolver=messaging.threshold_resolver,
        pending_clarification_reader=messaging.pending_clarification_reader,
        pending_clarification_repository=(
            messaging.pending_clarification_repository
        ),
        audit_port=audit_port,
        refresh_port=refresh_port,
        originating_channel="WEB",
    )


async def _resolve_meeting_citations(
    *,
    meeting_reader: MeetingReader,
    actor: ActorContext,
    response: CalendarConversationResponse,
) -> list[ResolvedCitation]:
    """Resolve a calendar response's ``meeting`` citations to titles (D131).

    Resolution reads through the same Meeting reader the cell answers from
    (no second read path). A citation whose meeting can no longer load
    falls back to a short-hex label rather than leaking a raw id.
    """
    if not response.cited_artefacts:
        return []
    meetings = await meeting_reader.list_meetings(
        tenant_context=actor.tenant_context, include_cancelled=True
    )
    titles = {m.id: (m.title or None) for m in meetings}
    resolved: list[ResolvedCitation] = []
    for citation in response.cited_artefacts:
        ref = _short_hex(citation.artefact_id)
        title = titles.get(citation.artefact_id)
        label = title if title else f"meeting {ref}"
        resolved.append(ResolvedCitation(type="meeting", label=label, ref=ref))
    return resolved


async def _calendar_result_from_state(
    *,
    meeting_reader: MeetingReader,
    actor: ActorContext,
    state: ConversationState,
) -> ConversationTurnResult:
    """Map a calendar cell ``ConversationState`` to the stateless web turn result."""
    response: CalendarConversationResponse = state.payload["calendar_response"]
    citations = await _resolve_meeting_citations(
        meeting_reader=meeting_reader, actor=actor, response=response
    )
    reply = response.text
    if response.staleness_note:
        reply = f"{reply}\n\n⚠ {response.staleness_note}"
    return ConversationTurnResult(
        conversation_id=state.conversation_id,
        purpose=state.purpose,
        turn_count=state.turn_count,
        is_open=state.is_open,
        cell_payload=None,
        reply=reply,
        citations=citations,
    )


async def open_calendar_conversation_with_reader(
    *,
    messaging: MessagingComposition,
    audit_port: AuditPort,
    actor: ActorContext,
    meeting_reader: MeetingReader,
    refresh_port: object | None,
    focus_id: UUID,
) -> ConversationTurnResult | None:
    """Open a calendar conversation given an injected reader (the testable core).

    Returns ``None`` when the focus Meeting does not exist for the actor
    (the router maps that to 404). The opening turn is the cell's real
    resolution path on ``"show me {title}"`` (FindByTitle, REAL_TIME), which
    grounds on the clicked meeting at dogfooding scale. The infra-wiring
    wrapper (``open_calendar_conversation``) supplies the reader + refresh.
    """
    meetings = await meeting_reader.list_meetings(
        tenant_context=actor.tenant_context, include_cancelled=True
    )
    focus = next((m for m in meetings if m.id == focus_id), None)
    if focus is None:
        return None
    cell = build_calendar_cell(
        messaging=messaging,
        audit_port=audit_port,
        actor=actor,
        meeting_reader=meeting_reader,
        refresh_port=refresh_port,
    )
    state = await cell.open(
        ConversationInvocation(
            purpose=_CALENDAR_PURPOSE, actor_id=actor.actor_id
        )
    )
    title = focus.title or "(untitled meeting)"
    state = await cell.turn(state, ConversationInput(text=f"show me {title}"))
    return await _calendar_result_from_state(
        meeting_reader=meeting_reader, actor=actor, state=state
    )


async def advance_calendar_conversation_with_reader(
    *,
    messaging: MessagingComposition,
    audit_port: AuditPort,
    actor: ActorContext,
    meeting_reader: MeetingReader,
    refresh_port: object | None,
    conversation_id: str,
    purpose: str,
    turn_count: int,
    text: str,
) -> ConversationTurnResult:
    """Advance a calendar conversation given an injected reader (the testable core).

    The calendar cell does not drill down, so no ``cell_payload`` is
    threaded; the cell reads its own ``PendingClarification`` from the
    user-scoped repo (D134/D139), exactly as on the messaging path.
    """
    cell = build_calendar_cell(
        messaging=messaging,
        audit_port=audit_port,
        actor=actor,
        meeting_reader=meeting_reader,
        refresh_port=refresh_port,
    )
    state_in = ConversationState(
        conversation_id=conversation_id,
        purpose=purpose or _CALENDAR_PURPOSE,
        turn_count=turn_count,
        is_open=True,
        payload={},
    )
    state = await cell.turn(state_in, ConversationInput(text=text))
    return await _calendar_result_from_state(
        meeting_reader=meeting_reader, actor=actor, state=state
    )


async def open_calendar_conversation(
    *,
    messaging: MessagingComposition,
    audit_port: AuditPort,
    actor: ActorContext,
    focus_id: UUID,
) -> ConversationTurnResult | None:
    """Infra wrapper: build the per-tenant calendar collaborators, then open.

    Exercised at the live smoke (it builds real per-tenant infrastructure);
    the reader-injected core above carries the unit-tested logic.
    """
    meeting_reader, resolve_connection_id = _build_calendar_collaborators(actor)
    refresh_port = await _build_refresh_port(actor, resolve_connection_id)
    return await open_calendar_conversation_with_reader(
        messaging=messaging,
        audit_port=audit_port,
        actor=actor,
        meeting_reader=meeting_reader,
        refresh_port=refresh_port,
        focus_id=focus_id,
    )


async def advance_calendar_conversation(
    *,
    messaging: MessagingComposition,
    audit_port: AuditPort,
    actor: ActorContext,
    conversation_id: str,
    purpose: str,
    turn_count: int,
    text: str,
) -> ConversationTurnResult:
    """Infra wrapper: build the per-tenant calendar collaborators, then advance."""
    meeting_reader, resolve_connection_id = _build_calendar_collaborators(actor)
    refresh_port = await _build_refresh_port(actor, resolve_connection_id)
    return await advance_calendar_conversation_with_reader(
        messaging=messaging,
        audit_port=audit_port,
        actor=actor,
        meeting_reader=meeting_reader,
        refresh_port=refresh_port,
        conversation_id=conversation_id,
        purpose=purpose,
        turn_count=turn_count,
        text=text,
    )


async def _build_refresh_port(actor: ActorContext, resolve_connection_id):
    """Build the D150 refresh port when a google-calendar connection exists."""
    from apps.cli._calendar import build_calendar_refresh_adapter

    connection_id = await resolve_connection_id()
    if connection_id is None:
        return None
    return build_calendar_refresh_adapter(
        tenant_id=str(actor.tenant_context.tenant_id),
        connection_id=connection_id,
    )


__all__ = [
    "FOCUS_KIND_CALENDAR",
    "FOCUS_KIND_CASE",
    "ConversationTurnResult",
    "ResolvedCitation",
    "advance_calendar_conversation",
    "advance_calendar_conversation_with_reader",
    "advance_conversation",
    "build_calendar_cell",
    "build_mirror_cell",
    "open_calendar_conversation",
    "open_calendar_conversation_with_reader",
    "open_conversation",
]
