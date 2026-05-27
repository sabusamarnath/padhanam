"""AuditConversationCell — the audit-conversation ConversationFlow implementer (D115, D131, D134, D138, D139, P14, S51).

The audit-conversation cell is the second ConversationFlow implementer
(the first was the manual entry cell at S46). It composes the existing
``AuditEventReader`` port from S36 with the D137-shape audit-intent
classification primitive at ``shared_kernel/intent_classification_audit.py``
and the D131/D135/D138 response-composition pattern at the
``AuditConversationResponse`` value object.

Three-case confidence discipline at D134:

- *Case 1 (high)*: execute the audit query against the
  ``AuditEventReader`` and compose a cited response.
- *Case 2 (medium)*: render a shape-aware clarification phrased as a
  question proposing the specific query; persist a
  ``PendingClarification``; do not query.
- *Case 3 (low / parse failure)*: render the generic UnclearAuditIntent
  clarification; do not query.

Resolution-ambiguity routing per D139 (cross-cutting promotion of the
S50 manual-entry-cell pattern): when ``FindByCase`` or
``FindByCombination``'s ``case_reference`` resolves to multiple cases,
the cell renders the numbered candidate list and persists a
PendingClarification carrying the candidates; the operator's positional
reply (a bare integer) selects the candidate and the query proceeds.

Per pre-write reconciliation Finding 1 (S51 framing), the cell consumes
the existing ``contexts.audit.ports.reader.AuditEventReader`` rather
than introducing a new port. Per Finding 5 (S51 build, option c), the
inbound webhook dispatch decision (which cell handles an inbound
message) defers to S52; S51 lands the cell at the context layer with
contract-harness registration plus a script-driven smoke.

A ``turn`` returns a ``ConversationState`` with the rendered reply
embedded in ``payload``: ``response_text`` (the rendered string),
``audit_response`` (the structured ``AuditConversationResponse`` with
D131/D138 citation fields), ``intent_class``, and ``confidence_band``.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID, uuid4

from contexts.audit.domain.audit_event_record import AuditEventRecord
from contexts.audit.domain.ports import AuditPort
from contexts.audit.domain.query_filters import (
    AuditEventListFilters,
    AuditEventListPage,
)
from contexts.audit.ports.reader import AuditEventReader

from contexts.audit_conversation.application.ports.portfolio_case_lookup import (
    AuditCaseSummary,
    PortfolioCaseLookup,
)
from contexts.audit_conversation.application.query_builder import (
    build_filters_for_actor,
    build_filters_for_case,
    build_filters_for_combination,
    build_filters_for_date_range,
    build_filters_for_event_type,
)
from contexts.audit_conversation.application.response import (
    AuditConversationResponse,
)
from contexts.audit_conversation.domain.intent import (
    AuditIntent,
    AuditIntentType,
    FindByActor,
    FindByCase,
    FindByCombination,
    FindByDateRange,
    FindByEventType,
    UnclearAuditIntent,
    audit_intent_type_of,
    parse_audit_intent,
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
from shared_kernel.conversation_flow import ArtefactCitation
from shared_kernel.intent_classification_audit import (
    AUDIT_INTENT_EXTRACTION_SCHEMA,
    build_audit_extraction_prompt,
)


# Pending clarification proposed_intent shape:
#   {"intent_class": str, ...fields from the AuditIntent..., "purpose": "audit_query"}
# Plus an optional "resolution_candidates" sidecar for resolution-ambiguity.
_RESOLUTION_CANDIDATES_KEY = "resolution_candidates"
_PURPOSE = "audit_query"

# Confirming / correcting / positional-selection lexicons mirror the
# manual entry cell pattern at S47 / S50.
_CONFIRMING_REPLIES = frozenset(
    {"yes", "y", "confirm", "confirmed", "ok", "okay", "sure", "go ahead"}
)
_CORRECTING_REPLIES = frozenset(
    {"no", "n", "nope", "cancel", "stop", "wait", "actually"}
)

# Stopwords for case-reference token matching (mirrors messaging's
# resolve_target stopword set, audit-context-narrowed).
_CASE_STOPWORDS = frozenset(
    {
        "the", "a", "an", "my", "our", "this", "that", "these", "those",
        "to", "of", "for", "in", "on", "and", "or", "with", "about",
        "case", "cases", "audit", "events", "history", "log",
    }
)


def _normalise(text: str) -> str:
    return text.strip().lower().rstrip(".,!?")


def _classify_reply(text: str) -> str:
    """Classify a reply as confirm / cancel / fresh against an active pending."""
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
    """Parse a bare positive integer reply ("1", "2") to a 1-based index."""
    normalised = _normalise(text)
    if not normalised:
        return None
    try:
        value = int(normalised)
    except ValueError:
        return None
    return value if value > 0 else None


def _significant_case_tokens(text: str) -> frozenset[str]:
    """Lowercase, split on non-alphanumerics, drop case-context stopwords."""
    return frozenset(
        word
        for word in re.split(r"[^a-z0-9]+", text.lower())
        if word and word not in _CASE_STOPWORDS
    )


def _resolve_case_reference(
    reference: str, cases: tuple[AuditCaseSummary, ...]
) -> tuple[UUID | None, tuple[AuditCaseSummary, ...]]:
    """Resolve a natural-language case reference against the operator's cases.

    Returns ``(matched_id, ())`` on exactly-one match; ``(None, candidates)``
    on multi-match (top-scoring tie); ``(None, ())`` on no-match. The
    multi-match candidate tuple carries the tied cases for D139 resolution-
    ambiguity routing.
    """
    ref_tokens = _significant_case_tokens(reference)
    if not ref_tokens or not cases:
        return None, ()

    # Exact significant-token-set match wins outright when unique.
    exact = [
        c for c in cases if _significant_case_tokens(c.title) == ref_tokens
    ]
    if len(exact) == 1:
        return exact[0].case_id, ()

    scored = [
        (len(ref_tokens & _significant_case_tokens(c.title)), c)
        for c in cases
    ]
    best_score = max(score for score, _ in scored)
    if best_score == 0:
        return None, ()

    winners = tuple(c for score, c in scored if score == best_score)
    if len(winners) == 1:
        return winners[0].case_id, ()
    return None, winners


def _empty_response(text: str) -> AuditConversationResponse:
    """A clarification response with no citations."""
    return AuditConversationResponse(text=text)


class AuditConversationCell:
    """The audit-conversation ConversationFlow implementer (D138, S51).

    Implements the ``ConversationFlow`` Protocol structurally. Holds the
    six ports it consumes (structured-output, audit-event reader,
    portfolio case lookup, confidence calculator, threshold resolver,
    pending-clarification reader plus repository) plus the cell's own
    audit-event emission port.

    Tenant scoping flows through ``actor: ActorContext`` (the cell's
    constructor accepts a request-scoped actor); every port call routes
    the actor's tenant context.
    """

    def __init__(
        self,
        *,
        structured_output_port: StructuredOutputPort,
        audit_event_reader: AuditEventReader,
        portfolio_case_lookup: PortfolioCaseLookup,
        actor: ActorContext,
        confidence_calculator: ConfidenceCalculator,
        threshold_resolver: ThresholdResolver,
        pending_clarification_reader: PendingClarificationReader,
        pending_clarification_repository: PendingClarificationRepository,
        audit_port: AuditPort,
        originating_channel: str = "WHATSAPP",
        originating_intake_id: UUID | None = None,
        page_size: int = 10,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._structured_output = structured_output_port
        self._audit_reader = audit_event_reader
        self._case_lookup = portfolio_case_lookup
        self._actor = actor
        self._confidence = confidence_calculator
        self._thresholds = threshold_resolver
        self._pending_reader = pending_clarification_reader
        self._pending_repo = pending_clarification_repository
        self._audit_port = audit_port
        self._originating_channel = originating_channel
        self._originating_intake_id = originating_intake_id
        self._page_size = page_size
        self._clock = clock or (lambda: datetime.now(timezone.utc))

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

        # Check for an active PendingClarification first; if one exists,
        # try resolving it against the inbound reply.
        active = await self._pending_reader.get_active(
            tenant_id=self._actor.tenant_context.tenant_id,
            user_id=self._actor.actor_id,
        )

        if active is not None:
            # Positional-selection branch (resolution-ambiguity resolution)
            candidates = active.proposed_intent.get(
                _RESOLUTION_CANDIDATES_KEY
            )
            if candidates:
                selection = _parse_positional_selection(raw_text)
                if selection is not None and 1 <= selection <= len(candidates):
                    chosen = candidates[selection - 1]
                    return await self._handle_resolution_selection(
                        state=state,
                        active=active,
                        chosen=chosen,
                        raw_text=raw_text,
                    )

            # Confirm / cancel branch
            classification = _classify_reply(raw_text)
            if classification == "confirm":
                return await self._handle_pending_confirm(
                    state=state, active=active, raw_text=raw_text
                )
            if classification == "cancel":
                await expire_pending_clarification(
                    repository=self._pending_repo,
                    audit_port=self._audit_port,
                    actor=self._actor,
                    pending=active,
                )
                response = _empty_response(
                    "OK, cancelled. Send a new audit query when ready."
                )
                return self._render_turn_state(
                    state=state,
                    response=response,
                    intent_class="",
                    confidence_band="cancelled_pending",
                )
            # Fresh-turn fallback when reply does not confirm / cancel /
            # positional-select: expire the prior pending and treat
            # inbound as fresh.
            await expire_pending_clarification(
                repository=self._pending_repo,
                audit_port=self._audit_port,
                actor=self._actor,
                pending=active,
            )

        # Fresh turn: extract intent + confidence.
        try:
            intent, confidence = await self._extract_intent(raw_text)
        except StructuredOutputParseFailure:
            response = _empty_response(
                "I could not interpret that as an audit query. Try "
                "asking about events for a case, in a date range, by an "
                "actor, or of a specific event type."
            )
            return self._render_turn_state(
                state=state,
                response=response,
                intent_class="",
                confidence_band="parse_failure",
            )

        # Confidence dispatch.
        thresholds = self._thresholds.resolve(operation_class="audit_query")
        band = self._classify_confidence(confidence, thresholds)

        if band == "low" or isinstance(intent, UnclearAuditIntent):
            return await self._handle_unclear(
                state=state, intent=intent, raw_text=raw_text
            )

        if band == "medium":
            return await self._handle_medium_confidence(
                state=state, intent=intent, raw_text=raw_text
            )

        # High confidence: execute the audit query.
        return await self._handle_high_confidence(
            state=state, intent=intent, raw_text=raw_text
        )

    # ---------------------------------------------------------- intent extract
    async def _extract_intent(
        self, message: str
    ) -> tuple[AuditIntent, float]:
        request = StructuredOutputRequest(
            prompt=build_audit_extraction_prompt(message),
            schema=AUDIT_INTENT_EXTRACTION_SCHEMA,
            latency_tier=LatencyTier.REAL_TIME_REQUIRED,
            temperature=0.0,
        )
        result = await self._structured_output.generate_structured(request)
        intent = parse_audit_intent(result.value)
        confidence = self._confidence.compute(
            request=request, response=result
        )
        return intent, confidence

    def _classify_confidence(
        self, confidence: float, thresholds: Any
    ) -> str:
        if confidence >= thresholds.high:
            return "high"
        if confidence >= thresholds.medium:
            return "medium"
        return "low"

    # ----------------------------------------------------------- dispatch high
    async def _handle_high_confidence(
        self,
        *,
        state: ConversationState,
        intent: AuditIntent,
        raw_text: str,
    ) -> ConversationState:
        # FindByCase and FindByCombination with case_reference need case
        # resolution via portfolio lookup.
        if isinstance(intent, FindByCase):
            return await self._handle_find_by_case(state=state, intent=intent)

        if isinstance(intent, FindByCombination) and intent.case_reference:
            return await self._handle_find_by_combination_with_case(
                state=state, intent=intent
            )

        # Direct-filter intents skip case resolution.
        return await self._execute_and_compose(
            state=state, intent=intent, resolved_case_id=None
        )

    async def _handle_find_by_case(
        self, *, state: ConversationState, intent: FindByCase
    ) -> ConversationState:
        cases = await self._case_lookup.find_cases(actor=self._actor)
        matched_id, candidates = _resolve_case_reference(
            intent.case_reference, cases
        )

        if matched_id is not None:
            return await self._execute_and_compose(
                state=state, intent=intent, resolved_case_id=matched_id
            )

        if candidates:
            return await self._dispatch_resolution_clarify(
                state=state,
                intent=intent,
                candidates=candidates,
                reference=intent.case_reference,
            )

        response = _empty_response(
            f"I could not find a case matching “{intent.case_reference}”."
        )
        return self._render_turn_state(
            state=state,
            response=response,
            intent_class=AuditIntentType.FIND_BY_CASE.value,
            confidence_band="resolution_no_match",
        )

    async def _handle_find_by_combination_with_case(
        self, *, state: ConversationState, intent: FindByCombination
    ) -> ConversationState:
        cases = await self._case_lookup.find_cases(actor=self._actor)
        assert intent.case_reference is not None  # branch guard above
        matched_id, candidates = _resolve_case_reference(
            intent.case_reference, cases
        )

        if matched_id is not None:
            return await self._execute_and_compose(
                state=state, intent=intent, resolved_case_id=matched_id
            )

        if candidates:
            return await self._dispatch_resolution_clarify(
                state=state,
                intent=intent,
                candidates=candidates,
                reference=intent.case_reference,
            )

        response = _empty_response(
            f"I could not find a case matching “{intent.case_reference}”."
        )
        return self._render_turn_state(
            state=state,
            response=response,
            intent_class=AuditIntentType.FIND_BY_COMBINATION.value,
            confidence_band="resolution_no_match",
        )

    # ------------------------------------------------- execute and compose
    async def _execute_and_compose(
        self,
        *,
        state: ConversationState,
        intent: AuditIntent,
        resolved_case_id: UUID | None,
    ) -> ConversationState:
        try:
            filters = self._filters_for(
                intent=intent, resolved_case_id=resolved_case_id
            )
        except ValueError as exc:
            response = _empty_response(
                f"I could not build the audit query: {exc}."
            )
            return self._render_turn_state(
                state=state,
                response=response,
                intent_class=audit_intent_type_of(intent),
                confidence_band="filter_build_failure",
            )

        page = await self._audit_reader.list_audit_events_with_filters(
            destination="per_tenant",
            filters=filters,
            cursor=None,
            page_size=self._page_size,
            tenant_context=self._actor.tenant_context,
        )

        response = self._compose_response(intent=intent, page=page)
        return self._render_turn_state(
            state=state,
            response=response,
            intent_class=audit_intent_type_of(intent),
            confidence_band="high",
        )

    def _filters_for(
        self,
        *,
        intent: AuditIntent,
        resolved_case_id: UUID | None,
    ) -> AuditEventListFilters:
        now = self._clock()
        if isinstance(intent, FindByCase):
            assert resolved_case_id is not None
            return build_filters_for_case(
                intent, resolved_case_id=resolved_case_id
            )
        if isinstance(intent, FindByDateRange):
            return build_filters_for_date_range(intent, now=now)
        if isinstance(intent, FindByActor):
            return build_filters_for_actor(intent)
        if isinstance(intent, FindByEventType):
            return build_filters_for_event_type(intent)
        if isinstance(intent, FindByCombination):
            return build_filters_for_combination(
                intent, resolved_case_id=resolved_case_id, now=now
            )
        raise ValueError(
            f"Cannot build filters for intent type {type(intent).__name__}"
        )

    def _compose_response(
        self, *, intent: AuditIntent, page: AuditEventListPage
    ) -> AuditConversationResponse:
        if not page.events:
            return _empty_response(
                "No audit events matched that query."
            )

        intent_summary = _summarise_intent(intent)
        lines = [
            f"Audit events {intent_summary}: {len(page.events)} found."
        ]
        for event in page.events:
            lines.append(_summarise_event(event))

        text = "\n".join(lines)

        cited_audit_events = tuple(event.id for event in page.events)
        cited_artefacts = _artefact_citations_from(page.events)

        return AuditConversationResponse(
            text=text,
            cited_audit_events=cited_audit_events,
            cited_artefacts=cited_artefacts,
        )

    # ----------------------------------------------------- dispatch medium
    async def _handle_medium_confidence(
        self,
        *,
        state: ConversationState,
        intent: AuditIntent,
        raw_text: str,
    ) -> ConversationState:
        proposed_summary = _summarise_intent(intent)
        text = (
            f"It sounds like you want audit events {proposed_summary}. "
            "Confirm with 'yes' or correct me with 'no'."
        )
        await self._persist_pending(
            intent=intent,
            proposed_action_summary=f"audit_query {proposed_summary}",
            raw_text=raw_text,
            resolution_candidates=None,
        )
        response = _empty_response(text)
        return self._render_turn_state(
            state=state,
            response=response,
            intent_class=audit_intent_type_of(intent),
            confidence_band="medium",
        )

    # ----------------------------------------------------- dispatch unclear
    async def _handle_unclear(
        self,
        *,
        state: ConversationState,
        intent: AuditIntent,
        raw_text: str,
    ) -> ConversationState:
        clarification = (
            intent.clarification
            if isinstance(intent, UnclearAuditIntent)
            else (
                "I could not interpret that as an audit query. Try asking "
                "about events for a case, in a date range, by an actor, or "
                "of a specific event type."
            )
        )
        response = _empty_response(clarification)
        return self._render_turn_state(
            state=state,
            response=response,
            intent_class=AuditIntentType.UNCLEAR_AUDIT.value,
            confidence_band="low",
        )

    # --------------------------------------------------- resolution-ambig
    async def _dispatch_resolution_clarify(
        self,
        *,
        state: ConversationState,
        intent: AuditIntent,
        candidates: tuple[AuditCaseSummary, ...],
        reference: str,
    ) -> ConversationState:
        # Number the candidates; cite each via cited_artefacts per D139.
        numbered = [
            f"{idx + 1}. {c.title}"
            for idx, c in enumerate(candidates)
        ]
        text = (
            f"I found {len(candidates)} cases matching "
            f"“{reference}”. Which did you mean? Reply with a "
            "number.\n" + "\n".join(numbered)
        )

        cited_artefacts = tuple(
            ArtefactCitation(artefact_id=c.case_id, artefact_type="case")
            for c in candidates
        )

        await self._persist_pending(
            intent=intent,
            proposed_action_summary=(
                f"choose among {len(candidates)} cases matching "
                f"“{reference}”"
            ),
            raw_text=reference,
            resolution_candidates=[
                {"id": str(c.case_id), "label": c.title}
                for c in candidates
            ],
        )

        response = AuditConversationResponse(
            text=text,
            cited_artefacts=cited_artefacts,
        )
        return self._render_turn_state(
            state=state,
            response=response,
            intent_class=audit_intent_type_of(intent),
            confidence_band="resolution_ambiguous",
        )

    async def _handle_resolution_selection(
        self,
        *,
        state: ConversationState,
        active: PendingClarification,
        chosen: dict[str, Any],
        raw_text: str,
    ) -> ConversationState:
        chosen_id = UUID(chosen["id"])
        # Re-derive the intent from the pending; the pending's
        # proposed_intent dict carries the intent_class and slot values.
        intent = _intent_from_pending(active)

        await resolve_pending_clarification(
            repository=self._pending_repo,
            audit_port=self._audit_port,
            actor=self._actor,
            pending=active,
            resolution="confirmed",
        )

        return await self._execute_and_compose(
            state=state, intent=intent, resolved_case_id=chosen_id
        )

    # ------------------------------------------------------ pending confirm
    async def _handle_pending_confirm(
        self,
        *,
        state: ConversationState,
        active: PendingClarification,
        raw_text: str,
    ) -> ConversationState:
        intent = _intent_from_pending(active)

        await resolve_pending_clarification(
            repository=self._pending_repo,
            audit_port=self._audit_port,
            actor=self._actor,
            pending=active,
            resolution="confirmed",
        )

        # On confirm of a medium-confidence pending, execute directly.
        # If the pending carried a case reference, attempt resolution
        # again (in case the operator confirms a single-match scenario).
        if isinstance(intent, FindByCase):
            return await self._handle_find_by_case(state=state, intent=intent)
        if isinstance(intent, FindByCombination) and intent.case_reference:
            return await self._handle_find_by_combination_with_case(
                state=state, intent=intent
            )

        return await self._execute_and_compose(
            state=state, intent=intent, resolved_case_id=None
        )

    # ----------------------------------------------------- persist pending
    async def _persist_pending(
        self,
        *,
        intent: AuditIntent,
        proposed_action_summary: str,
        raw_text: str,
        resolution_candidates: list[dict[str, str]] | None,
    ) -> None:
        proposed_intent: dict[str, Any] = _intent_to_dict(intent)
        if resolution_candidates is not None:
            proposed_intent[_RESOLUTION_CANDIDATES_KEY] = resolution_candidates

        # Per the manual_entry_cell precedent at S47/S50, the
        # PendingClarification's originating_intake_id field anchors to
        # the inbound webhook's IntakeRecord. When the cell is invoked
        # outside a webhook context (the S51 contract harness and the
        # script-driven smoke per Finding 5 disposition), mint a fresh
        # UUID so the foreign-key constraint at the migration is
        # technically satisfied — the smoke creates the corresponding
        # intake out of band when it lands at the live stack.
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
            target_cell="audit_conversation",
        )

    # ----------------------------------------------------- render helper
    def _render_turn_state(
        self,
        *,
        state: ConversationState,
        response: AuditConversationResponse,
        intent_class: str,
        confidence_band: str,
    ) -> ConversationState:
        return ConversationState(
            conversation_id=state.conversation_id,
            purpose=state.purpose,
            turn_count=state.turn_count + 1,
            is_open=True,
            payload={
                "audit_response": response,
                "response_text": response.text,
                "intent_class": intent_class,
                "confidence_band": confidence_band,
            },
        )


# ---------------------------------------------------------------- helpers


def _summarise_intent(intent: AuditIntent) -> str:
    """A short operator-facing phrase describing the query the cell will run."""
    if isinstance(intent, FindByCase):
        return f"for case “{intent.case_reference}”"
    if isinstance(intent, FindByDateRange):
        return f"in the {intent.range_keyword.replace('_', ' ')} window"
    if isinstance(intent, FindByActor):
        return f"authored by {intent.actor}"
    if isinstance(intent, FindByEventType):
        return f"of type {intent.event_type}"
    if isinstance(intent, FindByCombination):
        parts: list[str] = []
        if intent.case_reference:
            parts.append(f"for case “{intent.case_reference}”")
        if intent.range_keyword:
            parts.append(
                f"in the {intent.range_keyword.replace('_', ' ')} window"
            )
        if intent.actor:
            parts.append(f"authored by {intent.actor}")
        if intent.event_type:
            parts.append(f"of type {intent.event_type}")
        return ", ".join(parts) if parts else "(combination)"
    return "(unclear)"


def _summarise_event(event: AuditEventRecord) -> str:
    """Render a single audit event line for the response text."""
    stamp = event.timestamp.strftime("%Y-%m-%d %H:%M")
    return (
        f"- {stamp} {event.action_verb} by {event.actor} on "
        f"{event.resource_type}"
    )


def _artefact_citations_from(
    events: tuple[AuditEventRecord, ...],
) -> tuple[ArtefactCitation, ...]:
    """Heterogeneous artefact citations from the events' resource references.

    Per S51 framing Finding 4 (symmetric-with-mirror shape): each event
    referencing a Case or DataPoint contributes a typed citation. We
    deduplicate by (resource_type, resource_id) so the same case
    appearing in multiple events cites once.
    """
    seen: set[tuple[str, str]] = set()
    citations: list[ArtefactCitation] = []
    for event in events:
        resource_type = event.resource_type
        if resource_type not in ("case", "data_point"):
            continue
        key = (resource_type, event.resource_id)
        if key in seen:
            continue
        seen.add(key)
        try:
            artefact_id = UUID(event.resource_id)
        except ValueError:
            continue
        citations.append(
            ArtefactCitation(
                artefact_id=artefact_id, artefact_type=resource_type
            )
        )
    return tuple(citations)


def _intent_to_dict(intent: AuditIntent) -> dict[str, Any]:
    """Serialize a typed AuditIntent into the PendingClarification dict shape."""
    base = {"intent_class": audit_intent_type_of(intent), "purpose": _PURPOSE}
    if isinstance(intent, FindByCase):
        return {**base, "case_reference": intent.case_reference}
    if isinstance(intent, FindByDateRange):
        return {**base, "range_keyword": intent.range_keyword}
    if isinstance(intent, FindByActor):
        return {**base, "actor": intent.actor}
    if isinstance(intent, FindByEventType):
        return {**base, "event_type": intent.event_type}
    if isinstance(intent, FindByCombination):
        return {
            **base,
            "case_reference": intent.case_reference or "",
            "range_keyword": intent.range_keyword or "",
            "actor": intent.actor or "",
            "event_type": intent.event_type or "",
        }
    return base


def _intent_from_pending(active: PendingClarification) -> AuditIntent:
    """Re-derive an AuditIntent from a stored PendingClarification dict."""
    raw = dict(active.proposed_intent)
    raw.pop(_RESOLUTION_CANDIDATES_KEY, None)
    raw.pop("purpose", None)
    return parse_audit_intent(raw)


__all__ = ["AuditConversationCell"]
