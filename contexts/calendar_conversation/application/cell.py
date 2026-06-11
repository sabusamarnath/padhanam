"""CalendarConversationCell — the calendar-conversation ConversationFlow implementer (D115, D131, D134, D138, D139, D148, P15, S55b-1).

The third ConversationFlow implementer (after the manual entry cell at
S46, audit-conversation at S51, and mirror-conversation at S52). It
mirrors the audit-conversation cell: a D137-shape calendar-intent
classification primitive at
``shared_kernel/intent_classification_calendar.py``, the D134 three-case
confidence discipline, D139 resolution-ambiguity routing through
``PendingClarification``, and the D131/D138 ``CalendarConversationResponse``
citing Meetings with the ``meeting`` discriminator (D148).

The cell consumes calendar's existing ``MeetingReader`` (the audit-
conversation precedent of consuming the producer reader rather than
introducing a parallel port). Refresh-before-answer (D150) lands at
commit 3 as an injected refresh port called at turn-open; this commit
queries the stored Meeting cache directly.

Resolution-ambiguity (D139): when ``FindByTitle``'s ``title_reference``
resolves to multiple meetings, the cell renders a numbered candidate list
and persists a PendingClarification carrying the candidates; the
operator's positional reply (a bare integer) selects one and the query
proceeds.

A ``turn`` returns a ``ConversationState`` with the rendered reply
embedded in ``payload``: ``response_text``, ``calendar_response`` (the
structured ``CalendarConversationResponse``), ``intent_class``, and
``confidence_band``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID, uuid4

from contexts.calendar.domain.meeting import Meeting
from contexts.calendar.ports.meeting_repository import MeetingReader

from contexts.calendar_conversation.application.audit_events import (
    draft_meeting_citation_event,
)
from contexts.calendar_conversation.application.ports.calendar_refresh import (
    CalendarRefreshError,
    CalendarRefreshPort,
)

from contexts.calendar_conversation.application.query_builder import (
    meetings_in_window,
    meetings_with_attendee,
    next_meeting,
    resolve_title_reference,
    resolve_window,
)
from contexts.calendar_conversation.application.response import (
    CalendarConversationResponse,
    meeting_citation,
)
from contexts.calendar_conversation.domain.intent import (
    CalendarIntent,
    CalendarIntentType,
    FindByAttendee,
    FindByDateRange,
    FindByTitle,
    FindNextMeeting,
    UnclearCalendarIntent,
    calendar_intent_type_of,
    parse_calendar_intent,
)

from contexts.messaging.api import (
    PendingClarification,
    PendingClarificationReader,
    PendingClarificationRepository,
    create_pending_clarification,
    expire_pending_clarification,
    resolve_pending_clarification,
)

from shared_kernel import (
    ActorContext,
    ActorReference,
    ConfidenceCalculator,
    ConversationClosure,
    ConversationInput,
    ConversationInvocation,
    ConversationOutcome,
    ConversationState,
    LatencyTier,
    StructuredOutputParseFailure,
    StructuredOutputPort,
    StructuredOutputRequest,
    ThresholdResolver,
)
from shared_kernel.intent_classification_calendar import (
    CALENDAR_INTENT_EXTRACTION_SCHEMA,
    build_calendar_extraction_prompt,
)

_log = logging.getLogger(__name__)

# D178 background refresh: process-global state so a fire-and-forget refresh
# survives the request that scheduled it and so rapid successive opens do not
# stampede overlapping full syncs of the same tenant's calendar.
#   _INFLIGHT_REFRESH — tenant ids with a refresh currently running.
#   _BACKGROUND_TASKS — strong refs to the live tasks (asyncio holds only weak
#     refs, so a task without a strong ref can be GC'd mid-flight).
_INFLIGHT_REFRESH: set[str] = set()
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()

_RESOLUTION_CANDIDATES_KEY = "resolution_candidates"
_PURPOSE = "calendar_query"
_OPERATION_CLASS = "calendar_query"
_TARGET_CELL = "calendar_conversation"

_CONFIRMING_REPLIES = frozenset(
    {"yes", "y", "confirm", "confirmed", "ok", "okay", "sure", "go ahead"}
)
_CORRECTING_REPLIES = frozenset(
    {"no", "n", "nope", "cancel", "stop", "wait", "actually"}
)

_UNCLEAR_FALLBACK = (
    "I could not interpret that as a calendar query. Try asking what's on "
    "your calendar today or this week, about meetings with a person, about "
    "a specific meeting by name, or for your next meeting."
)


def _normalise(text: str) -> str:
    return text.strip().lower().rstrip(".,!?")


def _classify_reply(text: str) -> str:
    normalised = _normalise(text)
    if normalised in _CONFIRMING_REPLIES:
        return "confirm"
    if normalised in _CORRECTING_REPLIES:
        return "cancel"
    first_token = normalised.split(" ", 1)[0] if normalised else ""
    if first_token in _CORRECTING_REPLIES:
        return "cancel"
    return "fresh"


def _parse_positional_selection(text: str) -> int | None:
    normalised = _normalise(text)
    if not normalised:
        return None
    try:
        value = int(normalised)
    except ValueError:
        return None
    return value if value > 0 else None


def _empty_response(text: str) -> CalendarConversationResponse:
    return CalendarConversationResponse(text=text)


class CalendarConversationCell:
    """The calendar-conversation ConversationFlow implementer (D138, D148, S55b-1)."""

    def __init__(
        self,
        *,
        structured_output_port: StructuredOutputPort,
        meeting_reader: MeetingReader,
        actor: ActorContext,
        confidence_calculator: ConfidenceCalculator,
        threshold_resolver: ThresholdResolver,
        pending_clarification_reader: PendingClarificationReader,
        pending_clarification_repository: PendingClarificationRepository,
        audit_port: Any,
        refresh_port: CalendarRefreshPort | None = None,
        refresh_timeout_seconds: float = 2.0,
        originating_channel: str = "WHATSAPP",
        originating_intake_id: UUID | None = None,
        page_size: int = 10,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._structured_output = structured_output_port
        self._meeting_reader = meeting_reader
        self._actor = actor
        self._confidence = confidence_calculator
        self._thresholds = threshold_resolver
        self._pending_reader = pending_clarification_reader
        self._pending_repo = pending_clarification_repository
        self._audit_port = audit_port
        self._refresh_port = refresh_port
        self._refresh_timeout = refresh_timeout_seconds
        self._originating_channel = originating_channel
        self._originating_intake_id = originating_intake_id
        self._page_size = page_size
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._staleness_note: str | None = None
        # The background refresh task scheduled this turn (D178), or None when
        # none was scheduled (no port, or a refresh for this tenant is already
        # in flight). Held so tests can deterministically await the refresh.
        self._refresh_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------ open
    async def open(
        self, invocation: ConversationInvocation
    ) -> ConversationState:
        return ConversationState(
            conversation_id=str(uuid4()),
            purpose=invocation.purpose or _PURPOSE,
            turn_count=0,
            is_open=True,
            payload={},
        )

    # ----------------------------------------------------------------- close
    async def close(
        self, state: ConversationState, closure: ConversationClosure
    ) -> ConversationOutcome:
        return ConversationOutcome(
            conversation_id=state.conversation_id,
            turn_count=state.turn_count,
            resolution=closure.reason,
        )

    # ------------------------------------------------------------------ turn
    async def turn(
        self, state: ConversationState, user_input: ConversationInput
    ) -> ConversationState:
        raw_text = user_input.text

        # Refresh-before-answer (D150 Option A): refresh the calendar within
        # the tier budget before querying; on timeout or failure, fall back
        # to the cached store and carry a staleness note onto any answer.
        await self._maybe_refresh()

        active = await self._pending_reader.get_active(
            tenant_id=self._actor.tenant_context.tenant_id,
            user_id=self._actor.actor_id,
        )

        if active is not None:
            candidates = active.proposed_intent.get(_RESOLUTION_CANDIDATES_KEY)
            if candidates:
                selection = _parse_positional_selection(raw_text)
                if selection is not None and 1 <= selection <= len(candidates):
                    chosen = candidates[selection - 1]
                    return await self._handle_resolution_selection(
                        state=state, active=active, chosen=chosen
                    )

            classification = _classify_reply(raw_text)
            if classification == "cancel":
                await expire_pending_clarification(
                    repository=self._pending_repo,
                    audit_port=self._audit_port,
                    actor=self._actor,
                    pending=active,
                    now=self._clock(),
                )
                return self._render_turn_state(
                    state=state,
                    response=_empty_response(
                        "OK, cancelled. Send a new calendar query when ready."
                    ),
                    intent_class="",
                    confidence_band="cancelled_pending",
                )
            # Confirm or fresh: expire the prior pending and treat inbound
            # as a fresh query (a calendar query has no write to confirm).
            await expire_pending_clarification(
                repository=self._pending_repo,
                audit_port=self._audit_port,
                actor=self._actor,
                pending=active,
                now=self._clock(),
            )

        try:
            intent, confidence = await self._extract_intent(raw_text)
        except StructuredOutputParseFailure:
            return self._render_turn_state(
                state=state,
                response=_empty_response(_UNCLEAR_FALLBACK),
                intent_class="",
                confidence_band="parse_failure",
            )

        thresholds = self._thresholds.resolve(operation_class=_OPERATION_CLASS)
        band = self._classify_confidence(confidence, thresholds)

        if band == "low" or isinstance(intent, UnclearCalendarIntent):
            return await self._handle_unclear(state=state, intent=intent)

        if band == "medium":
            return await self._handle_medium_confidence(
                state=state, intent=intent
            )

        return await self._handle_high_confidence(state=state, intent=intent)

    # ------------------------------------------------------------- refresh
    async def _maybe_refresh(self) -> None:
        """Kick a calendar refresh in the background (D178, revising D150 A).

        The open serves the cached Meeting store immediately — no synchronous
        wait, no staleness caveat — and a fire-and-forget refresh updates the
        store for the next turn. The refresh runs the D149 full sync, which
        cannot fit a per-open budget at real corpus scale; blocking on it
        (D150 Option A) taxed every open the full budget and fell back to
        cache anyway, so backgrounding removes both the latency and the
        always-on "timed out" warning while keeping the data near-fresh.

        Process-global dedup (``_INFLIGHT_REFRESH``) keeps rapid successive
        opens from stampeding overlapping full syncs of the same tenant's
        calendar. The task never raises into the request: failures are
        swallowed with a warning (the store simply stays as it was).
        """
        self._staleness_note = None
        self._refresh_task = None
        if self._refresh_port is None:
            return
        key = str(self._actor.tenant_context.tenant_id)
        if key in _INFLIGHT_REFRESH:
            return
        _INFLIGHT_REFRESH.add(key)
        task = asyncio.create_task(self._run_background_refresh(key))
        self._refresh_task = task
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)

    async def _run_background_refresh(self, key: str) -> None:
        """Run the scheduled refresh; never propagate, always release the key."""
        try:
            await self._refresh_port.refresh(
                tenant_context=self._actor.tenant_context
            )
        except CalendarRefreshError as exc:
            _log.warning("background calendar refresh unavailable: %s", exc)
        except Exception as exc:  # fire-and-forget: must never crash the loop
            _log.warning("background calendar refresh failed: %s", exc)
        finally:
            _INFLIGHT_REFRESH.discard(key)

    # ---------------------------------------------------------- intent extract
    async def _extract_intent(
        self, message: str
    ) -> tuple[CalendarIntent, float]:
        request = StructuredOutputRequest(
            prompt=build_calendar_extraction_prompt(message),
            schema=CALENDAR_INTENT_EXTRACTION_SCHEMA,
            latency_tier=LatencyTier.REAL_TIME_REQUIRED,
            temperature=0.0,
        )
        result = await self._structured_output.generate_structured(request)
        intent = parse_calendar_intent(result.value)
        confidence = self._confidence.compute(request=request, response=result)
        return intent, confidence

    def _classify_confidence(self, confidence: float, thresholds: Any) -> str:
        if confidence >= thresholds.high:
            return "high"
        if confidence >= thresholds.medium:
            return "medium"
        return "low"

    # ----------------------------------------------------------- dispatch high
    async def _handle_high_confidence(
        self, *, state: ConversationState, intent: CalendarIntent
    ) -> ConversationState:
        if isinstance(intent, FindByTitle):
            return await self._handle_find_by_title(state=state, intent=intent)
        return await self._execute_and_compose(state=state, intent=intent)

    async def _handle_find_by_title(
        self, *, state: ConversationState, intent: FindByTitle
    ) -> ConversationState:
        meetings = await self._meeting_reader.list_meetings(
            tenant_context=self._actor.tenant_context
        )
        matched, candidates = resolve_title_reference(
            intent.title_reference, meetings
        )
        if matched is not None:
            response = await self._compose_and_emit(
                [matched], summary=f"“{intent.title_reference}”"
            )
            return self._render_turn_state(
                state=state,
                response=response,
                intent_class=CalendarIntentType.FIND_BY_TITLE.value,
                confidence_band="high",
            )
        if candidates:
            return await self._dispatch_resolution_clarify(
                state=state,
                intent=intent,
                candidates=candidates,
                reference=intent.title_reference,
            )
        return self._render_turn_state(
            state=state,
            response=_empty_response(
                f"I could not find a meeting matching “{intent.title_reference}”."
            ),
            intent_class=CalendarIntentType.FIND_BY_TITLE.value,
            confidence_band="resolution_no_match",
        )

    async def _execute_and_compose(
        self, *, state: ConversationState, intent: CalendarIntent
    ) -> ConversationState:
        now = self._clock()
        meetings = await self._meeting_reader.list_meetings(
            tenant_context=self._actor.tenant_context
        )

        if isinstance(intent, FindByDateRange):
            try:
                start, end = resolve_window(intent.range_keyword, now=now)
            except ValueError:
                return self._render_turn_state(
                    state=state,
                    response=_empty_response(
                        "I did not recognise that time window. Try today, "
                        "tomorrow, this week, next week, or this month."
                    ),
                    intent_class=CalendarIntentType.FIND_BY_DATE_RANGE.value,
                    confidence_band="filter_build_failure",
                )
            matched = meetings_in_window(meetings, start=start, end=end)
            summary = f"in the {intent.range_keyword.replace('_', ' ')} window"
            intent_class = CalendarIntentType.FIND_BY_DATE_RANGE.value
        elif isinstance(intent, FindByAttendee):
            matched = meetings_with_attendee(meetings, attendee=intent.attendee)
            summary = f"with {intent.attendee}"
            intent_class = CalendarIntentType.FIND_BY_ATTENDEE.value
        elif isinstance(intent, FindNextMeeting):
            nxt = next_meeting(meetings, now=now)
            matched = (nxt,) if nxt is not None else ()
            summary = "next up"
            intent_class = CalendarIntentType.FIND_NEXT_MEETING.value
        else:
            return await self._handle_unclear(state=state, intent=intent)

        response = await self._compose_and_emit(
            list(matched[: self._page_size]), summary=summary
        )
        return self._render_turn_state(
            state=state,
            response=response,
            intent_class=intent_class,
            confidence_band="high",
        )

    async def _compose_and_emit(
        self, meetings: list[Meeting], *, summary: str
    ) -> CalendarConversationResponse:
        """Compose a cited answer and freeze its citation evidence (D148 option b).

        When meetings are cited, emit a ``meeting_citation`` audit event
        carrying an immutable, plaintext-free snapshot of each cited
        Meeting (sensitive content envelope-encrypted per D21). The live
        Meeting row remains the mutable search cache; this snapshot is the
        evidence record, frozen by the append-only audit chain.
        """
        response = self._compose(meetings, summary=summary)
        if meetings:
            await self._audit_port.emit(
                draft_meeting_citation_event(
                    tenant_context=self._actor.tenant_context,
                    actor=ActorReference(user_id=self._actor.actor_id),
                    meetings=tuple(meetings),
                    emitted_at=self._clock().isoformat(),
                )
            )
        return response

    def _compose(
        self, meetings: list[Meeting], *, summary: str
    ) -> CalendarConversationResponse:
        # The answer is drawn from the (possibly cached) Meeting store; if
        # the turn's refresh fell back, the staleness note rides along (D150).
        note = self._staleness_note
        if not meetings:
            return CalendarConversationResponse(
                text=f"No meetings {summary}.", staleness_note=note
            )
        lines = [f"Meetings {summary}: {len(meetings)} found."]
        for m in meetings:
            lines.append(_summarise_meeting(m))
        cited = tuple(meeting_citation(m.id) for m in meetings)
        return CalendarConversationResponse(
            text="\n".join(lines), cited_artefacts=cited, staleness_note=note
        )

    # ----------------------------------------------------- dispatch medium
    async def _handle_medium_confidence(
        self, *, state: ConversationState, intent: CalendarIntent
    ) -> ConversationState:
        proposed = _summarise_intent(intent)
        text = (
            f"It sounds like you want meetings {proposed}. "
            "Confirm with 'yes' or correct me with 'no'."
        )
        await self._persist_pending(
            intent=intent,
            proposed_action_summary=f"calendar_query {proposed}",
            resolution_candidates=None,
        )
        return self._render_turn_state(
            state=state,
            response=_empty_response(text),
            intent_class=calendar_intent_type_of(intent),
            confidence_band="medium",
        )

    # ----------------------------------------------------- dispatch unclear
    async def _handle_unclear(
        self, *, state: ConversationState, intent: CalendarIntent
    ) -> ConversationState:
        clarification = (
            intent.clarification
            if isinstance(intent, UnclearCalendarIntent)
            else _UNCLEAR_FALLBACK
        )
        return self._render_turn_state(
            state=state,
            response=_empty_response(clarification),
            intent_class=CalendarIntentType.UNCLEAR_CALENDAR.value,
            confidence_band="low",
        )

    # --------------------------------------------------- resolution-ambig
    async def _dispatch_resolution_clarify(
        self,
        *,
        state: ConversationState,
        intent: FindByTitle,
        candidates: tuple[Meeting, ...],
        reference: str,
    ) -> ConversationState:
        numbered = [
            f"{idx + 1}. {m.title}" for idx, m in enumerate(candidates)
        ]
        text = (
            f"I found {len(candidates)} meetings matching “{reference}”. "
            "Which did you mean? Reply with a number.\n" + "\n".join(numbered)
        )
        cited = tuple(meeting_citation(m.id) for m in candidates)
        await self._persist_pending(
            intent=intent,
            proposed_action_summary=(
                f"choose among {len(candidates)} meetings matching “{reference}”"
            ),
            resolution_candidates=[
                {
                    "id": str(m.id),
                    "label": m.title or "(untitled)",
                    "event_id": m.google_event_id,
                }
                for m in candidates
            ],
        )
        return self._render_turn_state(
            state=state,
            response=CalendarConversationResponse(text=text, cited_artefacts=cited),
            intent_class=CalendarIntentType.FIND_BY_TITLE.value,
            confidence_band="resolution_ambiguous",
        )

    async def _handle_resolution_selection(
        self,
        *,
        state: ConversationState,
        active: PendingClarification,
        chosen: dict[str, Any],
    ) -> ConversationState:
        await resolve_pending_clarification(
            repository=self._pending_repo,
            audit_port=self._audit_port,
            actor=self._actor,
            pending=active,
            resolution="confirmed",
        )
        meeting = await self._meeting_reader.get_by_event_id(
            tenant_context=self._actor.tenant_context,
            google_event_id=str(chosen.get("event_id", "")),
        )
        if meeting is None:
            return self._render_turn_state(
                state=state,
                response=_empty_response(
                    "That meeting is no longer available."
                ),
                intent_class=CalendarIntentType.FIND_BY_TITLE.value,
                confidence_band="resolution_stale",
            )
        response = await self._compose_and_emit(
            [meeting], summary=f"“{chosen.get('label', '')}”"
        )
        return self._render_turn_state(
            state=state,
            response=response,
            intent_class=CalendarIntentType.FIND_BY_TITLE.value,
            confidence_band="resolution_selected",
        )

    # ----------------------------------------------------- persist pending
    async def _persist_pending(
        self,
        *,
        intent: CalendarIntent,
        proposed_action_summary: str,
        resolution_candidates: list[dict[str, str]] | None,
    ) -> None:
        proposed_intent: dict[str, Any] = _intent_to_dict(intent)
        if resolution_candidates is not None:
            proposed_intent[_RESOLUTION_CANDIDATES_KEY] = resolution_candidates
        originating_intake_id = (
            self._originating_intake_id
            if self._originating_intake_id is not None
            else uuid4()
        )
        await create_pending_clarification(
            repository=self._pending_repo,
            audit_port=self._audit_port,
            actor=self._actor,
            user_id=self._actor.actor_id,
            originating_channel=self._originating_channel,
            originating_user_address=self._actor.actor_id,
            originating_intake_id=originating_intake_id,
            proposed_intent=proposed_intent,
            proposed_action_summary=proposed_action_summary,
            target_cell=_TARGET_CELL,
        )

    # ----------------------------------------------------- render helper
    def _render_turn_state(
        self,
        *,
        state: ConversationState,
        response: CalendarConversationResponse,
        intent_class: str,
        confidence_band: str,
    ) -> ConversationState:
        return ConversationState(
            conversation_id=state.conversation_id,
            purpose=state.purpose,
            turn_count=state.turn_count + 1,
            is_open=True,
            payload={
                "calendar_response": response,
                "response_text": response.text,
                "intent_class": intent_class,
                "confidence_band": confidence_band,
            },
        )


# ---------------------------------------------------------------- helpers


def _summarise_intent(intent: CalendarIntent) -> str:
    if isinstance(intent, FindByDateRange):
        return f"in the {intent.range_keyword.replace('_', ' ')} window"
    if isinstance(intent, FindByAttendee):
        return f"with {intent.attendee}"
    if isinstance(intent, FindByTitle):
        return f"matching “{intent.title_reference}”"
    if isinstance(intent, FindNextMeeting):
        return "for your next meeting"
    return "(unclear)"


def _summarise_meeting(meeting: Meeting) -> str:
    when = (
        meeting.start_at.strftime("%Y-%m-%d %H:%M")
        if meeting.start_at is not None
        else (meeting.start_raw or "(time unknown)")
    )
    title = meeting.title or "(untitled)"
    return f"- {when} {title}"


def _intent_to_dict(intent: CalendarIntent) -> dict[str, Any]:
    base = {"intent_class": calendar_intent_type_of(intent), "purpose": _PURPOSE}
    if isinstance(intent, FindByDateRange):
        return {**base, "range_keyword": intent.range_keyword}
    if isinstance(intent, FindByAttendee):
        return {**base, "attendee": intent.attendee}
    if isinstance(intent, FindByTitle):
        return {**base, "title_reference": intent.title_reference}
    return base


__all__ = ["CalendarConversationCell"]
