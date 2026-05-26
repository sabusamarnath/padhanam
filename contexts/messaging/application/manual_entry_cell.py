"""ManualEntryCell — the first ConversationFlow implementer (D115, D129, D134).

The manual entry cell is the Phase 2-A Wave 1 end-to-end exercise of
the substrate: the operator types portfolio state into a WhatsApp
message, and the cell parses, resolves, persists, and replies with a
cited confirmation.

It implements the ``ConversationFlow`` Protocol (D115) and is the
first implementer registered with the S45 contract harness. It lives
at the messaging *application* layer — not the domain layer the S46
framing brief named — because it holds ports and orchestrates, which
the ``layers-messaging`` hexagonal contract forbids a pure-domain
object (S46 pre-write reconciliation Finding B).

**S47 (D134): confidence-aware three-case discipline.** Each ``turn``
extracts intent via structured output, runs the ConfidenceCalculator
port over the response, and dispatches by confidence band:

- *Case 1 (confidence ≥ high cut-off)*: proceed with the
  orchestration; emit the cited confirmation.
- *Case 2 (medium ≤ confidence < high cut-off)*: render a shape-aware
  clarification phrased as a question proposing the specific action;
  persist a PendingClarification; do not write to the portfolio.
- *Case 3 (confidence < medium cut-off, or structured-output parse
  failure per D130 extension)*: render the generic UnclearIntent
  clarification; do not write.

**Multi-turn via PendingClarificationReader.** At turn-open the cell
consults the consumer port for any active PendingClarification for
``(tenant_id, user_id)``. When one exists:

- A confirming reply ("yes" / "confirm" / "that's right") resolves
  the pending and executes the proposed action.
- A correcting reply ("no" / "actually" / "wait") resolves the
  pending as cancelled and treats the inbound as a fresh turn.
- An ambiguous reply falls back to fresh-turn handling per the
  Phase 2-A operator-dogfooding-pragmatic disposition.

D115's ConversationFlow Protocol stays single-turn; multi-turn
behaviour emerges from the cell's port-mediated state consultation.

A ``turn`` returns a ``ConversationState`` with the rendered reply
embedded in ``payload``: ``response_text`` (the rendered WhatsApp
string), ``cell_response`` (the structured ``CellResponse`` with
D131 citation fields), ``intent_type``, and ``confidence_band``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from contexts.audit.domain.ports import AuditPort

from contexts.messaging.application.cell_response import (
    CellResponse,
    render_for_whatsapp,
)
from contexts.messaging.application.create_pending_clarification import (
    create_pending_clarification,
)
from contexts.messaging.application.expire_pending_clarification import (
    expire_pending_clarification,
)
from contexts.messaging.application.ports.pending_clarification_reader import (
    PendingClarificationReader,
)
from contexts.messaging.application.ports.portfolio_gateway import (
    CaseSummary,
    PortfolioGateway,
)
from contexts.messaging.application.resolve_pending_clarification import (
    resolve_pending_clarification,
)
from contexts.messaging.application.resolve_target import (
    ResolutionOutcome,
    ResolutionStatus,
    TargetCandidate,
    resolve_target,
)
from contexts.messaging.domain.intent import (
    AddDataPointIntent,
    CreateCaseIntent,
    Intent,
    IntentType,
    ReviseDataPointIntent,
    UnclearIntent,
    parse_intent,
)
from contexts.messaging.domain.pending_clarification import (
    PendingClarification,
)
from contexts.messaging.ports.pending_clarification_repository import (
    PendingClarificationRepository,
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
from shared_kernel.intent_classification import (
    INTENT_EXTRACTION_SCHEMA,
    build_extraction_prompt,
)


def _data_point_phrase(data_point_type: str) -> str:
    """A human phrase for a DataPointType value ('GOAL' -> 'goal')."""
    return data_point_type.lower().replace("_", " ")


# Confirming and correcting reply lexicons (Phase 2-A pragmatic).
# Multi-turn reply classification at higher fidelity (LLM-routed
# disambiguation) is a Phase 2-B+ enhancement.
_CONFIRMING_REPLIES = frozenset(
    {
        "yes",
        "y",
        "confirm",
        "confirmed",
        "ok",
        "okay",
        "sure",
        "yes please",
        "that's right",
        "thats right",
        "go ahead",
    }
)
_CORRECTING_REPLIES = frozenset(
    {
        "no",
        "n",
        "nope",
        "cancel",
        "stop",
        "wait",
        "actually",
        "actually no",
        "that's wrong",
        "thats wrong",
        "not quite",
    }
)


def _normalise(text: str) -> str:
    return text.strip().lower().rstrip(".,!?")


def _classify_reply(text: str) -> str:
    """Classify a reply against an active PendingClarification.

    Returns ``"confirm"`` if the reply confirms the pending,
    ``"cancel"`` if it corrects it, or ``"fresh"`` if it neither
    confirms nor corrects (the cell treats it as a fresh turn).
    """
    normalised = _normalise(text)
    if normalised in _CONFIRMING_REPLIES:
        return "confirm"
    if normalised in _CORRECTING_REPLIES:
        return "cancel"
    # Loose match on a leading correcting token ("actually let me...").
    first_token = normalised.split(" ", 1)[0] if normalised else ""
    if first_token in _CORRECTING_REPLIES:
        return "cancel"
    return "fresh"


# S50: the proposed_intent key the cell embeds resolution-ambiguity
# candidates under when persisting a resolution-pending. Keyed off the
# standard intent shape so ``parse_intent`` ignores the sidecar.
_RESOLUTION_CANDIDATES_KEY = "resolution_candidates"


def _parse_positional_selection(text: str) -> int | None:
    """Parse a bare positional-selection reply ("1", "2", "3").

    Returns the 1-based index the operator named, or ``None`` when the
    reply is not a bare positive integer. The narrow surface
    (whole-message integer only) is the Phase 2-A positional-only
    scope; descriptive forms ("the older one") defer per the S50
    framing-time scope decision.
    """
    normalised = _normalise(text)
    if not normalised:
        return None
    try:
        value = int(normalised)
    except ValueError:
        return None
    return value if value > 0 else None


def _format_relative_time(when: datetime, *, now: datetime) -> str:
    """Format ``when`` relative to ``now`` for operator-facing rendering.

    Returns short phrasing tuned for the Phase 2-A dogfooding window:
    "just now" (<1 minute), "Nm ago" (<1 hour), "Nh ago" (<24 hours),
    "N days ago" (<30 days), or the absolute date "YYYY-MM-DD"
    thereafter. The cell uses these strings as ``CaseSummary``
    discriminators so the operator can pick among same-titled cases
    by *when*.
    """
    delta = now - when
    seconds = delta.total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    days = int(seconds // 86400)
    if days < 30:
        return f"{days} day{'s' if days != 1 else ''} ago"
    return when.strftime("%Y-%m-%d")


def _case_discriminators(
    case: CaseSummary, *, now: datetime
) -> tuple[str, ...]:
    """Compose the disambiguating signals the operator picks against.

    Three signals at Phase 2-A: creation time (relative or absolute),
    last activity (relative or absolute), data-point count. Picked at
    framing because they answer the operator's "which one is this?"
    question without surfacing UUIDs or other opaque identifiers.
    """
    created = _format_relative_time(case.created_at, now=now)
    last_activity = _format_relative_time(case.last_activity_at, now=now)
    count = case.data_point_count
    points = f"{count} data point{'s' if count != 1 else ''}"
    return (f"created {created}", points, f"last activity {last_activity}")


def _render_numbered_candidates(
    candidates: tuple[TargetCandidate, ...],
) -> str:
    """Render the AMBIGUOUS-case candidates as a numbered list.

    Each line carries the candidate's label and a comma-joined
    discriminator string the operator scans visually before replying
    with the positional index. The rendering is channel-agnostic per
    D135; the WhatsApp channel surfaces this string as-is.
    """
    lines: list[str] = []
    for index, candidate in enumerate(candidates, start=1):
        if candidate.discriminators:
            suffix = " — " + ", ".join(candidate.discriminators)
        else:
            suffix = ""
        lines.append(f"{index}. {candidate.label}{suffix}")
    return "\n".join(lines)


class ManualEntryCell:
    """The first ConversationFlow implementer (D115) — manual entry.

    Constructed per request with the operator ``ActorContext`` the
    webhook synthesised. ``conversation_id`` lives on the
    ``ConversationState`` so it is stable across turns without the
    cell holding mutable state.

    Per the S47 addendum: the cell consumes confidence cut-offs via
    the ``ThresholdResolver`` port at turn time; the source carries
    no numeric threshold literals.
    """

    def __init__(
        self,
        *,
        structured_output_port: StructuredOutputPort,
        portfolio_gateway: PortfolioGateway,
        actor: ActorContext,
        confidence_calculator: ConfidenceCalculator,
        threshold_resolver: ThresholdResolver,
        pending_clarification_reader: PendingClarificationReader,
        pending_clarification_repository: PendingClarificationRepository,
        audit_port: AuditPort,
        originating_channel: str = "WHATSAPP",
        originating_intake_id: UUID | None = None,
    ) -> None:
        self._structured_output = structured_output_port
        self._gateway = portfolio_gateway
        self._actor = actor
        self._confidence = confidence_calculator
        self._thresholds = threshold_resolver
        self._pending_reader = pending_clarification_reader
        self._pending_repo = pending_clarification_repository
        self._audit_port = audit_port
        self._originating_channel = originating_channel
        # S47 smoke fix: the cell uses the webhook's actual inbound
        # intake_id for any PendingClarification it creates, so the
        # `fk_pending_clar_intake_id` FK to intakes(id) is satisfied.
        # Optional for backward compatibility with tests that don't
        # need the multi-turn path; the Case 2 dispatch path requires it.
        self._originating_intake_id = originating_intake_id

    async def open(
        self, invocation: ConversationInvocation
    ) -> ConversationState:
        """Start a manual-entry conversation; return the initial state."""
        return ConversationState(
            conversation_id=uuid4().hex,
            purpose=invocation.purpose,
            turn_count=0,
            is_open=True,
            payload={},
        )

    async def turn(
        self, state: ConversationState, user_input: ConversationInput
    ) -> ConversationState:
        """Process one inbound message; return the next state.

        Order of operations:
        1. Consult PendingClarificationReader for an active PENDING
           for the operator. If one exists and the reply confirms,
           resolve the pending and execute the proposed action; if
           the reply corrects, resolve the pending as cancelled and
           fall through to fresh-turn handling; otherwise fall
           through to fresh-turn handling.
        2. Extract structured intent from the inbound text. A
           StructuredOutputParseFailure routes to Case 3 directly.
        3. Compute confidence via the ConfidenceCalculator port.
        4. Dispatch by confidence band per D134's three-case
           discipline.
        """
        message = user_input.text
        tenant_id = UUID(self._actor.tenant_context.tenant_id)
        user_id = self._actor.actor_id

        # 1. Resolve any active PendingClarification first.
        active = await self._pending_reader.get_active(
            tenant_id=tenant_id, user_id=user_id
        )
        if active is not None:
            if datetime.now(timezone.utc) >= active.expires_at:
                # Lazy expiry sweep: the reader returned a stale
                # PENDING whose window elapsed; close the audit
                # transition cleanly before treating the inbound as
                # a fresh turn.
                await expire_pending_clarification(
                    repository=self._pending_repo,
                    audit_port=self._audit_port,
                    actor=self._actor,
                    pending=active,
                )
            else:
                # S50: a resolution-ambiguity pending carries the
                # numbered candidates the operator picks against. A
                # bare-integer reply ("1", "2", ...) is interpreted as
                # the positional selection. Other reply shapes
                # (confirm/cancel/fresh) continue to the standard
                # classification path below — operator can still cancel
                # a resolution-ambiguity pending with "no".
                if _RESOLUTION_CANDIDATES_KEY in active.proposed_intent:
                    selection = _parse_positional_selection(message)
                    if selection is not None:
                        return await self._handle_resolution_selection(
                            state,
                            active,
                            selection=selection,
                            raw_text=message,
                        )
                resolution = _classify_reply(message)
                if resolution == "confirm":
                    return await self._handle_confirmed_pending(
                        state, active, raw_text=message
                    )
                if resolution == "cancel":
                    await resolve_pending_clarification(
                        repository=self._pending_repo,
                        audit_port=self._audit_port,
                        actor=self._actor,
                        pending=active,
                        resolution="cancelled",
                    )
                    # Fall through to fresh-turn handling on the
                    # correcting inbound — operator-pragmatic.
                # ambiguous ("fresh") replies fall through to extract;
                # the active pending stays PENDING until the next
                # confirming reply, an explicit cancel, or expiry.

        # 2. Extract intent. Parse failure routes to Case 3.
        try:
            intent, confidence = await self._extract_intent(message)
        except StructuredOutputParseFailure:
            return self._emit(
                state,
                response=_clarification(_UNCLEAR_FALLBACK_TEXT),
                intent_type=IntentType.UNCLEAR.value,
                confidence_band="parse_failure",
            )

        # 3. Dispatch by confidence band.
        if isinstance(intent, UnclearIntent):
            return self._emit(
                state,
                response=_clarification(intent.clarification),
                intent_type=IntentType.UNCLEAR.value,
                confidence_band="low",
            )

        # Resolve thresholds through the port at turn time. Phase 2-A
        # single-pair adapter ignores ``operation_class``; Phase 2-B+
        # per-operation-class adapter activates as adapter swap.
        thresholds = self._thresholds.resolve(operation_class=None)

        if confidence >= thresholds.high:
            response = await self._dispatch_proceed(intent, raw_text=message)
            return self._emit(
                state,
                response=response,
                intent_type=_intent_type_of(intent),
                confidence_band="high",
            )

        if confidence >= thresholds.medium:
            response = await self._dispatch_clarify_with_pending(
                intent, raw_text=message
            )
            return self._emit(
                state,
                response=response,
                intent_type=_intent_type_of(intent),
                confidence_band="medium",
            )

        return self._emit(
            state,
            response=_clarification(_UNCLEAR_FALLBACK_TEXT),
            intent_type=_intent_type_of(intent),
            confidence_band="low",
        )

    async def close(
        self, state: ConversationState, closure: ConversationClosure
    ) -> ConversationOutcome:
        """Terminate the conversation; return the terminal outcome."""
        return ConversationOutcome(
            conversation_id=state.conversation_id,
            turn_count=state.turn_count,
            resolution=closure.reason or "closed",
            payload={},
        )

    def _emit(
        self,
        state: ConversationState,
        *,
        response: CellResponse,
        intent_type: str,
        confidence_band: str,
    ) -> ConversationState:
        rendered = render_for_whatsapp(
            response, composed_at=datetime.now(timezone.utc)
        )
        return ConversationState(
            conversation_id=state.conversation_id,
            purpose=state.purpose,
            turn_count=state.turn_count + 1,
            is_open=True,
            payload={
                "response_text": rendered,
                "cell_response": response,
                "intent_type": intent_type,
                "confidence_band": confidence_band,
            },
        )

    async def _extract_intent(
        self, message: str
    ) -> tuple[Intent, float]:
        """Extract a typed intent plus a confidence value."""
        request = StructuredOutputRequest(
            prompt=build_extraction_prompt(message),
            schema=INTENT_EXTRACTION_SCHEMA,
            latency_tier=LatencyTier.REAL_TIME_REQUIRED,
            temperature=0.0,
        )
        result = await self._structured_output.generate_structured(request)
        intent = parse_intent(result.value)
        confidence = self._confidence.compute(
            request=request, response=result
        )
        return intent, confidence

    async def _dispatch_proceed(
        self, intent: Intent, *, raw_text: str
    ) -> CellResponse:
        """Case 1: high confidence — execute the proposed action."""
        if isinstance(intent, CreateCaseIntent):
            return await self._handle_create_case(intent, raw_text=raw_text)
        if isinstance(intent, AddDataPointIntent):
            return await self._handle_add_data_point(intent, raw_text=raw_text)
        if isinstance(intent, ReviseDataPointIntent):
            return await self._handle_revise_data_point(
                intent, raw_text=raw_text
            )
        return _clarification(intent.clarification)

    async def _dispatch_clarify_with_pending(
        self, intent: Intent, *, raw_text: str
    ) -> CellResponse:
        """Case 2: medium confidence — clarification plus PendingClarification.

        The cell uses the webhook-recorded inbound IntakeRecord's id as
        the pending's ``originating_intake_id`` (threaded via
        ``__init__``). This satisfies the migration's FK constraint
        ``fk_pending_clar_intake_id`` on intakes(id) and gives the
        pending a structurally-honest anchor back to the message that
        triggered the clarification. S47 smoke surfaced the FK
        violation that the original "mint a fresh UUID" comment
        anticipated but didn't resolve.
        """
        if isinstance(intent, CreateCaseIntent):
            summary = f"start a case for {intent.title!r}"
        elif isinstance(intent, AddDataPointIntent):
            phrase = _data_point_phrase(intent.data_point_type)
            summary = (
                f"add a {phrase} to {intent.case_reference!r}: "
                f"{intent.value_text}"
            )
        elif isinstance(intent, ReviseDataPointIntent):
            summary = (
                f"revise {intent.data_point_reference!r} to "
                f"{intent.value_text}"
            )
        else:
            return _clarification(intent.clarification)

        # Use the webhook-recorded inbound IntakeRecord's id; fall back
        # to a freshly-minted UUID only when no upstream id was threaded
        # (the test path that constructs the cell without one).
        originating_intake_id = (
            self._originating_intake_id
            if self._originating_intake_id is not None
            else uuid4()
        )

        pending = await create_pending_clarification(
            repository=self._pending_repo,
            audit_port=self._audit_port,
            actor=self._actor,
            user_id=self._actor.actor_id,
            originating_channel=self._originating_channel,
            originating_user_address=self._originating_channel,
            originating_intake_id=originating_intake_id,
            proposed_intent=_serialise_intent(intent),
            proposed_action_summary=summary,
        )

        question = (
            f"I think you want to {summary}. Is that right? "
            "(yes / no)"
        )
        return _clarification(question)

    async def _handle_confirmed_pending(
        self,
        state: ConversationState,
        active: PendingClarification,
        *,
        raw_text: str,
    ) -> ConversationState:
        """Resolve a PENDING as confirmed and execute the proposed action."""
        await resolve_pending_clarification(
            repository=self._pending_repo,
            audit_port=self._audit_port,
            actor=self._actor,
            pending=active,
            resolution="confirmed",
        )
        intent = parse_intent(active.proposed_intent)
        response = await self._dispatch_proceed(intent, raw_text=raw_text)
        return self._emit(
            state,
            response=response,
            intent_type=_intent_type_of(intent),
            confidence_band="confirmed_pending",
        )

    async def _dispatch_resolution_clarify_with_pending(
        self,
        *,
        intent: Intent,
        candidates: tuple[TargetCandidate, ...],
        reference: str,
        noun: str,
    ) -> CellResponse:
        """Persist a resolution-ambiguity pending and render the question.

        S50: high-confidence intent + multi-match resolution lands as a
        sub-case of D134 Case 2's shape-aware clarification surface.
        The pending's ``proposed_intent`` embeds the original intent
        fields (so ``parse_intent`` resolves the variant on selection)
        plus a sidecar ``resolution_candidates`` list mapping each
        positional index to a Case id. The operator's bare-integer
        reply at the next turn resolves the pending and dispatches the
        original action against the selected id.
        """
        serialised = _serialise_intent(intent)
        serialised[_RESOLUTION_CANDIDATES_KEY] = [
            {
                "id": str(c.id),
                "label": c.label,
                "discriminators": list(c.discriminators),
            }
            for c in candidates
        ]
        summary = (
            f"choose among {len(candidates)} {noun}s matching "
            f"“{reference}”"
        )

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
            originating_user_address=self._originating_channel,
            originating_intake_id=originating_intake_id,
            proposed_intent=serialised,
            proposed_action_summary=summary,
        )

        numbered = _render_numbered_candidates(candidates)
        question = (
            f"More than one {noun} matches “{reference}”. "
            f"Which did you mean?\n{numbered}\n"
            f"(reply with the number)"
        )
        return _clarification(question)

    async def _handle_resolution_selection(
        self,
        state: ConversationState,
        active: PendingClarification,
        *,
        selection: int,
        raw_text: str,
    ) -> ConversationState:
        """Resolve a resolution-ambiguity pending by positional selection.

        S50: the operator replied with a bare integer to a pending the
        cell created at multi-match dispatch. When the integer indexes
        a valid candidate the cell resolves the pending as confirmed,
        rewrites the original intent's natural-language reference to
        the selected candidate's label (so the second pass through
        ``resolve_target`` matches exactly), and dispatches the action.

        Out-of-range selections re-render the numbered clarification
        without touching the pending — the operator gets another chance
        without losing the choice surface. Cancel (``no``) continues to
        be handled at the standard ``_classify_reply`` branch above.
        """
        candidate_data = active.proposed_intent.get(
            _RESOLUTION_CANDIDATES_KEY, []
        )
        if not (1 <= selection <= len(candidate_data)):
            # Out-of-range positional reply — re-render the question
            # with the original numbering. The pending stays PENDING
            # so the operator can try again.
            candidates = _candidates_from_serialised(candidate_data)
            numbered = _render_numbered_candidates(candidates)
            question = (
                f"I only have {len(candidate_data)} option"
                f"{'s' if len(candidate_data) != 1 else ''} — "
                f"please reply with a number between 1 and "
                f"{len(candidate_data)}.\n{numbered}"
            )
            return self._emit(
                state,
                response=_clarification(question),
                intent_type=_intent_type_of(parse_intent(active.proposed_intent)),
                confidence_band="resolution_out_of_range",
            )

        chosen = candidate_data[selection - 1]
        # Resolve the pending as confirmed — the positional reply is
        # the operator's authorisation to proceed with the action
        # against the chosen candidate.
        await resolve_pending_clarification(
            repository=self._pending_repo,
            audit_port=self._audit_port,
            actor=self._actor,
            pending=active,
            resolution="confirmed",
        )

        # Strip the sidecar before re-parsing the intent (so the cell
        # dispatches against a clean intent shape) and inject the
        # chosen candidate's label as the natural-language reference
        # that the second pass through ``resolve_target`` matches
        # uniquely. The chosen UUID is the load-bearing selection; the
        # label-rewrite is the bridge through the existing dispatch
        # surface without adding a "pre-resolved id" code path.
        clean_intent_dict = {
            k: v
            for k, v in active.proposed_intent.items()
            if k != _RESOLUTION_CANDIDATES_KEY
        }
        if clean_intent_dict.get("intent_type") == IntentType.ADD_DATA_POINT:
            clean_intent_dict["case_reference"] = chosen["label"]
        elif (
            clean_intent_dict.get("intent_type") == IntentType.REVISE_DATA_POINT
        ):
            clean_intent_dict["data_point_reference"] = chosen["label"]
        # The cell re-fetches portfolio state through the gateway on
        # the dispatch path; resolution against the rewritten
        # reference picks the chosen candidate (its label is now
        # exact). When multiple cases share the *same* label the
        # rewrite is insufficient on its own; the dispatch path falls
        # back to AMBIGUOUS-via-id-match (the chosen UUID matches),
        # but the multi-match guard in this path means the operator
        # already disambiguated. The dispatch's resolve_target will
        # match against the exact label set; the cell records the
        # chosen candidate's id explicitly for the dispatch through
        # the resolved-by-selection short-circuit below.

        intent = parse_intent(clean_intent_dict)
        chosen_id_str = chosen.get("id", "")
        response = await self._dispatch_proceed_against_resolved(
            intent, raw_text=raw_text, resolved_id_hint=chosen_id_str
        )
        return self._emit(
            state,
            response=response,
            intent_type=_intent_type_of(intent),
            confidence_band="resolved_by_selection",
        )

    async def _dispatch_proceed_against_resolved(
        self,
        intent: Intent,
        *,
        raw_text: str,
        resolved_id_hint: str,
    ) -> CellResponse:
        """Proceed with the action using a pre-resolved id from selection.

        S50: when a resolution-ambiguity pending resolves by positional
        selection, the chosen candidate's UUID is already known.
        Bypassing the gateway re-fetch + resolve_target round-trip is
        cheap and avoids the small risk that portfolio state changed
        between the disambiguation turn and the selection turn (a
        candidate could have been added or relabeled). The id-hint
        path drives the orchestration directly; CreateCase intents
        cannot reach this dispatcher (resolution-ambiguity is only
        possible for Add/Revise intents) so they fall back to the
        standard path defensively.
        """
        try:
            resolved_uuid = UUID(resolved_id_hint)
        except (TypeError, ValueError):
            # Defensive fallback if the sidecar id was malformed —
            # the standard dispatch will surface the error path.
            return await self._dispatch_proceed(intent, raw_text=raw_text)

        if isinstance(intent, AddDataPointIntent):
            # Fetch case title for the cited confirmation — a small
            # find_cases pass is cheap; the case must still exist in
            # the operator's tenant for the orchestration to succeed.
            cases = await self._gateway.find_cases(actor=self._actor)
            chosen_case = next(
                (c for c in cases if c.case_id == resolved_uuid), None
            )
            if chosen_case is None:
                return _clarification(
                    f"I could not find that case any more — "
                    f"it may have been removed. Please try again."
                )
            outcome = await self._gateway.create_data_point(
                actor=self._actor,
                raw_text=raw_text,
                case_id=resolved_uuid,
                data_point_type=intent.data_point_type,
                value={"text": intent.value_text},
            )
            phrase = _data_point_phrase(intent.data_point_type)
            return CellResponse(
                text=(
                    f"Added a {phrase} to {chosen_case.title}: "
                    f"{intent.value_text}."
                ),
                cited_intake_records=(outcome.intake_id,),
                cited_artefacts=(outcome.data_point_id,),
            )
        if isinstance(intent, ReviseDataPointIntent):
            outcome = await self._gateway.revise_data_point(
                actor=self._actor,
                raw_text=raw_text,
                data_point_id=resolved_uuid,
                value={"text": intent.value_text},
            )
            return CellResponse(
                text=f"Revised the data point: {intent.value_text}.",
                cited_intake_records=(outcome.intake_id,),
                cited_artefacts=(outcome.data_point_id,),
            )
        # CreateCase and Unclear paths cannot reach here — the
        # multi-match guard only activates on Add/Revise. Fall back
        # defensively to the standard dispatch.
        return await self._dispatch_proceed(intent, raw_text=raw_text)

    async def _handle_create_case(
        self, intent: CreateCaseIntent, *, raw_text: str
    ) -> CellResponse:
        """Create a Case directly — a new case has nothing to resolve."""
        outcome = await self._gateway.create_case(
            actor=self._actor, raw_text=raw_text, title=intent.title
        )
        return CellResponse(
            text=f"Recorded a new case: {outcome.title}.",
            cited_intake_records=(outcome.intake_id,),
            cited_artefacts=(outcome.case_id,),
        )

    async def _handle_add_data_point(
        self, intent: AddDataPointIntent, *, raw_text: str
    ) -> CellResponse:
        """Resolve the case reference, then add a DataPoint to it."""
        cases = await self._gateway.find_cases(actor=self._actor)
        # S50: build candidates carrying discriminators so an AMBIGUOUS
        # resolution can surface meaningful signals (creation time,
        # last activity, data-point count) for the operator to pick
        # against. The cell formats raw datetime/int fields from
        # ``CaseSummary`` into short strings per the channel-decides-
        # format pattern at D135.
        now = datetime.now(timezone.utc)
        candidates = [
            TargetCandidate(
                id=c.case_id,
                label=c.title,
                discriminators=_case_discriminators(c, now=now),
            )
            for c in cases
        ]
        resolution = resolve_target(intent.case_reference, candidates)
        if resolution.status is ResolutionStatus.AMBIGUOUS:
            # S50: high-confidence intent + multi-match resolution is a
            # sub-case of D134 Case 2 — render the shape-aware
            # clarification numbering the candidates and persist a
            # resolution-pending the operator's positional reply
            # resolves.
            return await self._dispatch_resolution_clarify_with_pending(
                intent=intent,
                candidates=resolution.candidates,
                reference=intent.case_reference,
                noun="case",
            )
        if resolution.status is ResolutionStatus.NO_MATCH:
            return _clarification(
                f"I could not find a case matching “{intent.case_reference}”."
            )
        assert resolution.matched_id is not None
        case_title = next(
            c.title for c in cases if c.case_id == resolution.matched_id
        )
        outcome = await self._gateway.create_data_point(
            actor=self._actor,
            raw_text=raw_text,
            case_id=resolution.matched_id,
            data_point_type=intent.data_point_type,
            value={"text": intent.value_text},
        )
        phrase = _data_point_phrase(intent.data_point_type)
        return CellResponse(
            text=(
                f"Added a {phrase} to {case_title}: {intent.value_text}."
            ),
            cited_intake_records=(outcome.intake_id,),
            cited_artefacts=(outcome.data_point_id,),
        )

    async def _handle_revise_data_point(
        self, intent: ReviseDataPointIntent, *, raw_text: str
    ) -> CellResponse:
        """Resolve the data-point reference, then revise it."""
        data_points = await self._gateway.find_data_points(actor=self._actor)
        resolution = resolve_target(
            intent.data_point_reference,
            [
                TargetCandidate(id=d.data_point_id, label=d.label)
                for d in data_points
            ],
        )
        if resolution.status is not ResolutionStatus.MATCHED_SINGLE:
            return _resolution_clarification(
                resolution, intent.data_point_reference, noun="data point"
            )
        assert resolution.matched_id is not None
        outcome = await self._gateway.revise_data_point(
            actor=self._actor,
            raw_text=raw_text,
            data_point_id=resolution.matched_id,
            value={"text": intent.value_text},
        )
        return CellResponse(
            text=f"Revised the data point: {intent.value_text}.",
            cited_intake_records=(outcome.intake_id,),
            cited_artefacts=(outcome.data_point_id,),
        )


def _intent_type_of(intent: Intent) -> str:
    """The IntentType value for a typed intent (for the state payload)."""
    if isinstance(intent, CreateCaseIntent):
        return IntentType.CREATE_CASE.value
    if isinstance(intent, AddDataPointIntent):
        return IntentType.ADD_DATA_POINT.value
    if isinstance(intent, ReviseDataPointIntent):
        return IntentType.REVISE_DATA_POINT.value
    return IntentType.UNCLEAR.value


def _serialise_intent(intent: Intent) -> dict[str, Any]:
    """Serialise a typed intent back to its structured-output dict shape."""
    if isinstance(intent, CreateCaseIntent):
        return {
            "intent_type": "create_case",
            "title": intent.title,
            "case_reference": "",
            "data_point_type": "",
            "data_point_reference": "",
            "value_text": "",
            "clarification": "",
        }
    if isinstance(intent, AddDataPointIntent):
        return {
            "intent_type": "add_data_point",
            "title": "",
            "case_reference": intent.case_reference,
            "data_point_type": intent.data_point_type,
            "data_point_reference": "",
            "value_text": intent.value_text,
            "clarification": "",
        }
    if isinstance(intent, ReviseDataPointIntent):
        return {
            "intent_type": "revise_data_point",
            "title": "",
            "case_reference": "",
            "data_point_type": "",
            "data_point_reference": intent.data_point_reference,
            "value_text": intent.value_text,
            "clarification": "",
        }
    return {
        "intent_type": "unclear",
        "title": "",
        "case_reference": "",
        "data_point_type": "",
        "data_point_reference": "",
        "value_text": "",
        "clarification": intent.clarification,
    }


def _clarification(text: str) -> CellResponse:
    """A clarification response — text only, no citations (D131)."""
    return CellResponse(text=text)


_UNCLEAR_FALLBACK_TEXT = (
    "I could not tell what you would like me to do. Could you say a "
    "little more?"
)


def _resolution_clarification(
    resolution: ResolutionOutcome, reference: str, *, noun: str
) -> CellResponse:
    """Compose a clarification for an ambiguous or unresolved target.

    Used by the DataPoint resolution path at S50; Case resolution
    routes AMBIGUOUS to ``_dispatch_resolution_clarify_with_pending``
    directly so the operator gets the numbered-with-discriminators
    surface. The DataPoint path stays at the simpler text join until
    operator-dogfooding signal surfaces a second instance per the
    build-at-second-instance discipline.
    """
    if resolution.status is ResolutionStatus.AMBIGUOUS:
        options = ", ".join(c.label for c in resolution.candidates)
        return _clarification(
            f"More than one {noun} matches “{reference}” — "
            f"did you mean one of: {options}?"
        )
    return _clarification(
        f"I could not find a {noun} matching “{reference}”."
    )


def _candidates_from_serialised(
    serialised: list[dict[str, Any]],
) -> tuple[TargetCandidate, ...]:
    """Rebuild ``TargetCandidate`` instances from a pending's sidecar.

    The ``_RESOLUTION_CANDIDATES_KEY`` value in ``proposed_intent`` is
    a list of ``{"id": str, "label": str, "discriminators": list[str]}``
    dicts; this helper restores the typed tuple the rendering helper
    consumes. Used at re-render time for an out-of-range positional
    selection (the pending stays PENDING so the rebuild matters).
    """
    out: list[TargetCandidate] = []
    for entry in serialised:
        try:
            candidate_id = UUID(entry.get("id", ""))
        except (TypeError, ValueError):
            continue
        label = str(entry.get("label", ""))
        raw_discs = entry.get("discriminators") or []
        discriminators = tuple(str(d) for d in raw_discs)
        out.append(
            TargetCandidate(
                id=candidate_id,
                label=label,
                discriminators=discriminators,
            )
        )
    return tuple(out)


__all__ = ["ManualEntryCell"]
