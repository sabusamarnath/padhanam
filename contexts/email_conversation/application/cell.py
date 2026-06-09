"""EmailConversationCell — the email-conversation ConversationFlow implementer (D115, D134, D138, D139, D151, D152, P15, S56b).

The fifth ConversationFlow implementer, mirroring calendar_conversation:
the D137-shape email-intent classification primitive, the D134 three-case
confidence discipline, D139 resolution-ambiguity routing through
PendingClarification, refresh-before-answer (D152 Option A) through an
injected refresh port, and an ``EmailConversationResponse`` citing Emails
with the ``email`` discriminator **directly — no citation-time snapshot**
(D151: email content is immutable, unlike the calendar Meeting).

The cell consumes email's ``EmailReader`` and refreshes through the
injected ``EmailRefreshPort``; it never reaches through to ``sync_email``,
so the deferred background-sync optimization is an apps-composition wiring
swap, not a cell change.

A ``turn`` returns a ``ConversationState`` whose ``payload`` carries
``email_response`` (the structured response), ``response_text``,
``intent_class``, and ``confidence_band``.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID, uuid4

from contexts.email.domain.email import Email
from contexts.email.ports.email_repository import EmailReader

from contexts.email_conversation.application.ports.email_refresh import (
    EmailRefreshError,
    EmailRefreshPort,
)
from contexts.email_conversation.application.query_builder import (
    emails_from_sender,
    emails_in_window,
    recent_emails,
    resolve_subject_reference,
    resolve_window,
)
from contexts.email_conversation.application.response import (
    EmailConversationResponse,
    email_citation,
)
from contexts.email_conversation.domain.intent import (
    EmailIntent,
    EmailIntentType,
    FindByDateRange,
    FindBySubject,
    FindFromSender,
    FindRecent,
    UnclearEmailIntent,
    email_intent_type_of,
    parse_email_intent,
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
from shared_kernel.intent_classification_email import (
    EMAIL_INTENT_EXTRACTION_SCHEMA,
    build_email_extraction_prompt,
)

_RESOLUTION_CANDIDATES_KEY = "resolution_candidates"
_PURPOSE = "email_query"
_OPERATION_CLASS = "email_query"
_TARGET_CELL = "email_conversation"
_RECENT_LIMIT = 10

_CORRECTING_REPLIES = frozenset(
    {"no", "n", "nope", "cancel", "stop", "wait", "actually"}
)

_UNCLEAR_FALLBACK = (
    "I could not interpret that as an email query. Try asking what came in "
    "today or this week, about email from a person, or about a specific "
    "email by subject. (I can read your email but not send or reply.)"
)


def _normalise(text: str) -> str:
    return text.strip().lower().rstrip(".,!?")


def _classify_reply(text: str) -> str:
    normalised = _normalise(text)
    if normalised in _CORRECTING_REPLIES:
        return "cancel"
    first = normalised.split(" ", 1)[0] if normalised else ""
    return "cancel" if first in _CORRECTING_REPLIES else "fresh"


def _parse_positional_selection(text: str) -> int | None:
    normalised = _normalise(text)
    if not normalised:
        return None
    try:
        value = int(normalised)
    except ValueError:
        return None
    return value if value > 0 else None


def _empty(text: str, *, note: str | None = None) -> EmailConversationResponse:
    return EmailConversationResponse(text=text, staleness_note=note)


class EmailConversationCell:
    """The email-conversation ConversationFlow implementer (D138, D151, D152, S56b)."""

    def __init__(
        self,
        *,
        structured_output_port: StructuredOutputPort,
        email_reader: EmailReader,
        actor: ActorContext,
        confidence_calculator: ConfidenceCalculator,
        threshold_resolver: ThresholdResolver,
        pending_clarification_reader: PendingClarificationReader,
        pending_clarification_repository: PendingClarificationRepository,
        audit_port: Any,
        refresh_port: EmailRefreshPort | None = None,
        refresh_timeout_seconds: float = 2.0,
        originating_channel: str = "WHATSAPP",
        originating_intake_id: UUID | None = None,
        page_size: int = 10,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._structured_output = structured_output_port
        self._email_reader = email_reader
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

    async def open(self, invocation: ConversationInvocation) -> ConversationState:
        return ConversationState(
            conversation_id=str(uuid4()),
            purpose=invocation.purpose or _PURPOSE,
            turn_count=0,
            is_open=True,
            payload={},
        )

    async def close(
        self, state: ConversationState, closure: ConversationClosure
    ) -> ConversationOutcome:
        return ConversationOutcome(
            conversation_id=state.conversation_id,
            turn_count=state.turn_count,
            resolution=closure.reason,
        )

    async def turn(
        self, state: ConversationState, user_input: ConversationInput
    ) -> ConversationState:
        raw_text = user_input.text

        # Refresh-before-answer (D152 Option A) through the port at turn-open.
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
                    return await self._handle_resolution_selection(
                        state=state, active=active, chosen=candidates[selection - 1]
                    )
            if _classify_reply(raw_text) == "cancel":
                await expire_pending_clarification(
                    repository=self._pending_repo, audit_port=self._audit_port,
                    actor=self._actor, pending=active,
                    now=self._clock(),
                )
                return self._render(
                    state, _empty("OK, cancelled. Send a new email query when ready."),
                    "", "cancelled_pending",
                )
            await expire_pending_clarification(
                repository=self._pending_repo, audit_port=self._audit_port,
                actor=self._actor, pending=active,
                now=self._clock(),
            )

        try:
            intent, confidence = await self._extract_intent(raw_text)
        except StructuredOutputParseFailure:
            return self._render(state, _empty(_UNCLEAR_FALLBACK, note=self._staleness_note), "", "parse_failure")

        thresholds = self._thresholds.resolve(operation_class=_OPERATION_CLASS)
        band = self._classify_confidence(confidence, thresholds)

        if band == "low" or isinstance(intent, UnclearEmailIntent):
            return await self._handle_unclear(state=state, intent=intent)
        if band == "medium":
            return await self._handle_medium(state=state, intent=intent)
        return await self._handle_high(state=state, intent=intent)

    async def _maybe_refresh(self) -> None:
        self._staleness_note = None
        if self._refresh_port is None:
            return
        try:
            await asyncio.wait_for(
                self._refresh_port.refresh(tenant_context=self._actor.tenant_context),
                timeout=self._refresh_timeout,
            )
        except asyncio.TimeoutError:
            self._staleness_note = "Showing your cached email — the live refresh timed out."
        except EmailRefreshError:
            self._staleness_note = (
                "Showing your cached email — the live refresh is currently unavailable."
            )

    async def _extract_intent(self, message: str) -> tuple[EmailIntent, float]:
        request = StructuredOutputRequest(
            prompt=build_email_extraction_prompt(message),
            schema=EMAIL_INTENT_EXTRACTION_SCHEMA,
            latency_tier=LatencyTier.REAL_TIME_REQUIRED,
            temperature=0.0,
        )
        result = await self._structured_output.generate_structured(request)
        intent = parse_email_intent(result.value)
        confidence = self._confidence.compute(request=request, response=result)
        return intent, confidence

    def _classify_confidence(self, confidence: float, thresholds: Any) -> str:
        if confidence >= thresholds.high:
            return "high"
        if confidence >= thresholds.medium:
            return "medium"
        return "low"

    async def _handle_high(self, *, state: ConversationState, intent: EmailIntent) -> ConversationState:
        if isinstance(intent, FindBySubject):
            return await self._handle_find_by_subject(state=state, intent=intent)
        return await self._execute_and_compose(state=state, intent=intent)

    async def _handle_find_by_subject(
        self, *, state: ConversationState, intent: FindBySubject
    ) -> ConversationState:
        emails = await self._email_reader.list_emails(tenant_context=self._actor.tenant_context)
        matched, candidates = resolve_subject_reference(intent.subject_reference, emails)
        if matched is not None:
            return self._render(
                state, self._compose([matched], summary=f"“{intent.subject_reference}”"),
                EmailIntentType.FIND_BY_SUBJECT.value, "high",
            )
        if candidates:
            return await self._dispatch_resolution_clarify(
                state=state, intent=intent, candidates=candidates, reference=intent.subject_reference
            )
        return self._render(
            state, _empty(f"I could not find an email matching “{intent.subject_reference}”.", note=self._staleness_note),
            EmailIntentType.FIND_BY_SUBJECT.value, "resolution_no_match",
        )

    async def _execute_and_compose(self, *, state: ConversationState, intent: EmailIntent) -> ConversationState:
        now = self._clock()
        emails = await self._email_reader.list_emails(tenant_context=self._actor.tenant_context)
        if isinstance(intent, FindByDateRange):
            try:
                start, end = resolve_window(intent.range_keyword, now=now)
            except ValueError:
                return self._render(
                    state, _empty("I did not recognise that time window. Try today, yesterday, this week, last week, or this month.", note=self._staleness_note),
                    EmailIntentType.FIND_BY_DATE_RANGE.value, "filter_build_failure",
                )
            matched = emails_in_window(emails, start=start, end=end)
            summary = f"in the {intent.range_keyword.replace('_', ' ')} window"
            ic = EmailIntentType.FIND_BY_DATE_RANGE.value
        elif isinstance(intent, FindFromSender):
            matched = emails_from_sender(emails, sender=intent.sender)
            summary = f"from {intent.sender}"
            ic = EmailIntentType.FIND_FROM_SENDER.value
        elif isinstance(intent, FindRecent):
            matched = recent_emails(emails, limit=_RECENT_LIMIT)
            summary = "most recent"
            ic = EmailIntentType.FIND_RECENT.value
        else:
            return await self._handle_unclear(state=state, intent=intent)
        return self._render(state, self._compose(list(matched[: self._page_size]), summary=summary), ic, "high")

    def _compose(self, emails: list[Email], *, summary: str) -> EmailConversationResponse:
        note = self._staleness_note
        if not emails:
            return EmailConversationResponse(text=f"No emails {summary}.", staleness_note=note)
        lines = [f"Emails {summary}: {len(emails)} found."]
        for e in emails:
            lines.append(_summarise_email(e))
        cited = tuple(email_citation(e.id) for e in emails)
        return EmailConversationResponse(text="\n".join(lines), cited_artefacts=cited, staleness_note=note)

    async def _handle_medium(self, *, state: ConversationState, intent: EmailIntent) -> ConversationState:
        proposed = _summarise_intent(intent)
        await self._persist_pending(
            intent=intent, proposed_action_summary=f"email_query {proposed}", resolution_candidates=None
        )
        return self._render(
            state, _empty(f"It sounds like you want emails {proposed}. Confirm with 'yes' or correct me with 'no'.", note=self._staleness_note),
            email_intent_type_of(intent), "medium",
        )

    async def _handle_unclear(self, *, state: ConversationState, intent: EmailIntent) -> ConversationState:
        clar = intent.clarification if isinstance(intent, UnclearEmailIntent) else _UNCLEAR_FALLBACK
        return self._render(state, _empty(clar, note=self._staleness_note), EmailIntentType.UNCLEAR_EMAIL.value, "low")

    async def _dispatch_resolution_clarify(
        self, *, state: ConversationState, intent: FindBySubject, candidates: tuple[Email, ...], reference: str
    ) -> ConversationState:
        numbered = [f"{i + 1}. {e.subject}" for i, e in enumerate(candidates)]
        text = (
            f"I found {len(candidates)} emails matching “{reference}”. "
            "Which did you mean? Reply with a number.\n" + "\n".join(numbered)
        )
        cited = tuple(email_citation(e.id) for e in candidates)
        await self._persist_pending(
            intent=intent,
            proposed_action_summary=f"choose among {len(candidates)} emails matching “{reference}”",
            resolution_candidates=[
                {"id": str(e.id), "label": e.subject or "(no subject)", "message_id": e.message_id}
                for e in candidates
            ],
        )
        return self._render(
            state, EmailConversationResponse(text=text, cited_artefacts=cited, staleness_note=self._staleness_note),
            EmailIntentType.FIND_BY_SUBJECT.value, "resolution_ambiguous",
        )

    async def _handle_resolution_selection(
        self, *, state: ConversationState, active: PendingClarification, chosen: dict[str, Any]
    ) -> ConversationState:
        await resolve_pending_clarification(
            repository=self._pending_repo, audit_port=self._audit_port,
            actor=self._actor, pending=active, resolution="confirmed",
        )
        email = await self._email_reader.get_by_message_id(
            tenant_context=self._actor.tenant_context, message_id=str(chosen.get("message_id", ""))
        )
        if email is None:
            return self._render(state, _empty("That email is no longer available."), EmailIntentType.FIND_BY_SUBJECT.value, "resolution_stale")
        return self._render(state, self._compose([email], summary=f"“{chosen.get('label', '')}”"), EmailIntentType.FIND_BY_SUBJECT.value, "resolution_selected")

    async def _persist_pending(
        self, *, intent: EmailIntent, proposed_action_summary: str, resolution_candidates: list[dict[str, str]] | None
    ) -> None:
        proposed_intent = _intent_to_dict(intent)
        if resolution_candidates is not None:
            proposed_intent[_RESOLUTION_CANDIDATES_KEY] = resolution_candidates
        intake_id = self._originating_intake_id if self._originating_intake_id is not None else uuid4()
        await create_pending_clarification(
            repository=self._pending_repo, audit_port=self._audit_port, actor=self._actor,
            user_id=self._actor.actor_id, originating_channel=self._originating_channel,
            originating_user_address=self._actor.actor_id, originating_intake_id=intake_id,
            proposed_intent=proposed_intent, proposed_action_summary=proposed_action_summary,
            target_cell=_TARGET_CELL,
        )

    def _render(self, state: ConversationState, response: EmailConversationResponse, intent_class: str, band: str) -> ConversationState:
        return ConversationState(
            conversation_id=state.conversation_id,
            purpose=state.purpose,
            turn_count=state.turn_count + 1,
            is_open=True,
            payload={
                "email_response": response,
                "response_text": response.text,
                "intent_class": intent_class,
                "confidence_band": band,
            },
        )


def _summarise_intent(intent: EmailIntent) -> str:
    if isinstance(intent, FindByDateRange):
        return f"in the {intent.range_keyword.replace('_', ' ')} window"
    if isinstance(intent, FindFromSender):
        return f"from {intent.sender}"
    if isinstance(intent, FindBySubject):
        return f"matching “{intent.subject_reference}”"
    if isinstance(intent, FindRecent):
        return "most recent"
    return "(unclear)"


def _summarise_email(email: Email) -> str:
    when = email.received_at.strftime("%Y-%m-%d %H:%M") if email.received_at else "(date unknown)"
    subject = email.subject or "(no subject)"
    sender = email.from_address or "(unknown)"
    return f"- {when} {subject} — {sender}"


def _intent_to_dict(intent: EmailIntent) -> dict[str, Any]:
    base = {"intent_class": email_intent_type_of(intent), "purpose": _PURPOSE}
    if isinstance(intent, FindByDateRange):
        return {**base, "range_keyword": intent.range_keyword}
    if isinstance(intent, FindFromSender):
        return {**base, "sender": intent.sender}
    if isinstance(intent, FindBySubject):
        return {**base, "subject_reference": intent.subject_reference}
    return base


__all__ = ["EmailConversationCell"]
