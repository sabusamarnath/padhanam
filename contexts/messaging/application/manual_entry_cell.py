"""ManualEntryCell — the first ConversationFlow implementer (D115, D129, S46).

The manual entry cell is the Phase 2-A Wave 1 end-to-end exercise of
the substrate: the operator types portfolio state into a WhatsApp
message, and the cell parses, resolves, persists, and replies with a
cited confirmation.

It implements the ``ConversationFlow`` Protocol (D115) and is the
first implementer registered with the S45 contract harness. It lives
at the messaging *application* layer — not the domain layer the
framing brief named — because it holds ports and orchestrates, which
the ``layers-messaging`` hexagonal contract forbids a pure-domain
object (S46 pre-write reconciliation Finding B).

A ``turn`` processes one inbound message:

1. extract a typed intent via structured output (REAL_TIME_REQUIRED
   tier — the operator is waiting);
2. dispatch on the intent variant — ``CreateCaseIntent`` creates
   directly; ``AddDataPointIntent`` / ``ReviseDataPointIntent``
   resolve their natural-language target reference against portfolio
   state first; ``UnclearIntent`` returns a clarification;
3. drive the matching intake-canonical orchestration through the
   ``PortfolioGateway``;
4. compose a ``CellResponse`` carrying D131 citation fields and embed
   the rendered reply in the returned ``ConversationState``.

The cell is a per-request object: the webhook builds it with the
request's operator ``ActorContext``. DropCaseIntent, QueryStateIntent,
and multi-cell routing defer to the second-instance trigger.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from contexts.messaging.application.cell_response import (
    CellResponse,
    render_for_whatsapp,
)
from contexts.messaging.application.ports.portfolio_gateway import (
    PortfolioGateway,
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
from shared_kernel import (
    ActorContext,
    ConversationClosure,
    ConversationInput,
    ConversationInvocation,
    ConversationOutcome,
    ConversationState,
    LatencyTier,
    StructuredOutputPort,
    StructuredOutputRequest,
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
    "METHODOLOGY_APPLICATION."
)


def _extraction_prompt(message: str) -> str:
    """Build the structured-output prompt for intent extraction."""
    return f'{_EXTRACTION_PREAMBLE}\n\nThe operator sent: "{message}"'


def _data_point_phrase(data_point_type: str) -> str:
    """A human phrase for a DataPointType value ('GOAL' -> 'goal')."""
    return data_point_type.lower().replace("_", " ")


class ManualEntryCell:
    """The first ConversationFlow implementer (D115) — manual entry.

    Constructed per request with the operator ``ActorContext`` the
    webhook synthesised. ``conversation_id`` lives on the
    ``ConversationState`` so it is stable across turns without the
    cell holding mutable state.
    """

    def __init__(
        self,
        *,
        structured_output_port: StructuredOutputPort,
        portfolio_gateway: PortfolioGateway,
        actor: ActorContext,
    ) -> None:
        self._structured_output = structured_output_port
        self._gateway = portfolio_gateway
        self._actor = actor

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

        The composed reply is embedded in the returned state's
        ``payload``: ``response_text`` (the rendered WhatsApp string),
        ``cell_response`` (the structured ``CellResponse`` with D131
        citation fields), and ``intent_type``.
        """
        message = user_input.text
        intent = await self._extract_intent(message)
        response = await self._dispatch(intent, raw_text=message)
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
                "intent_type": _intent_type_of(intent),
            },
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

    async def _extract_intent(self, message: str) -> Intent:
        """Extract a typed intent from the message via structured output."""
        request = StructuredOutputRequest(
            prompt=_extraction_prompt(message),
            schema=INTENT_EXTRACTION_SCHEMA,
            latency_tier=LatencyTier.REAL_TIME_REQUIRED,
            temperature=0.0,
        )
        result = await self._structured_output.generate_structured(request)
        return parse_intent(result.value)

    async def _dispatch(self, intent: Intent, *, raw_text: str) -> CellResponse:
        """Dispatch a typed intent to the matching handler."""
        if isinstance(intent, CreateCaseIntent):
            return await self._handle_create_case(intent, raw_text=raw_text)
        if isinstance(intent, AddDataPointIntent):
            return await self._handle_add_data_point(intent, raw_text=raw_text)
        if isinstance(intent, ReviseDataPointIntent):
            return await self._handle_revise_data_point(
                intent, raw_text=raw_text
            )
        return _clarification(intent.clarification)

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


def _clarification(text: str) -> CellResponse:
    """A clarification response — text only, no citations (D131)."""
    return CellResponse(text=text)


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
