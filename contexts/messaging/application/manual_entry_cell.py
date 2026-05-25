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
    INTENT_EXTRACTION_SCHEMA,
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

_EXTRACTION_PREAMBLE = (
    "You extract a structured intent from a portfolio-management "
    "message a busy professional sent their assistant. Classify the "
    "message as create_case (start tracking a new case or item), "
    "add_data_point (record a goal, status, or methodology "
    "application against an existing case), revise_data_point (update "
    "an existing data point), or unclear (the message does not map "
    "cleanly to one of those). Fill only the fields relevant to the "
    "chosen intent; leave every other field as an empty string. For "
    "add_data_point, data_point_type is one of GOAL, STATUS, or "
    "METHODOLOGY_APPLICATION. Populate the confidence field with your "
    "self-reported confidence in the classification (0.0-1.0)."
)


def _extraction_prompt(message: str) -> str:
    """Build the structured-output prompt for intent extraction."""
    return f'{_EXTRACTION_PREAMBLE}\n\nThe operator sent: "{message}"'


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
            prompt=_extraction_prompt(message),
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

        The cell needs an ``originating_intake_id`` for the
        PendingClarification. The webhook layer recorded the inbound
        IntakeRecord before the cell ran (per D128 intake-canonical),
        but the cell does not currently hold that id. Phase 2-A
        compromise: mint a fresh UUID as the pending's
        ``originating_intake_id`` slot when no upstream intake id has
        been threaded through. The transitive-anchoring discipline at
        D135 (cited_intake_records anchors the audit chain) holds at
        the cell's confirmation reply; the pending's
        ``originating_intake_id`` is the *cell-level* intake reference,
        not the webhook-level one. P14 framing reconciles the two as
        the second-implementer trigger.
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

        # Phase 2-A: synthesise an originating intake id at the cell
        # altitude. Recorded as an honest limitation; P14 second-
        # instance trigger threads the webhook intake id through.
        originating_intake_id = uuid4()

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
        resolution = resolve_target(
            intent.case_reference,
            [TargetCandidate(id=c.case_id, label=c.title) for c in cases],
        )
        if resolution.status is not ResolutionStatus.MATCHED_SINGLE:
            return _resolution_clarification(
                resolution, intent.case_reference, noun="case"
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
    """Compose a clarification for an ambiguous or unresolved target."""
    if resolution.status is ResolutionStatus.AMBIGUOUS:
        options = ", ".join(resolution.candidate_labels)
        return _clarification(
            f"More than one {noun} matches “{reference}” — "
            f"did you mean one of: {options}?"
        )
    return _clarification(
        f"I could not find a {noun} matching “{reference}”."
    )


__all__ = ["ManualEntryCell"]
