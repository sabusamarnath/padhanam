"""MirrorConversationCell — the mirror-conversation ConversationFlow implementer (D115, D131, D134, D138, D139, D141, P14, S52).

The third ConversationFlow implementer at P14 close (manual entry cell
at S46; audit-conversation at S51; this at S52). Mirror-conversation
answers the operator's "what is the current state?" queries by
composing the portfolio read-side substrate (via the
``MirrorPortfolioReader`` consumer port from S52 commit 7) with the
intent-classification primitive at D137 and the D131/D135/D138
response-composition pattern.

Three-case confidence discipline at D134:

- *Case 1 (high)*: execute the mirror query and compose a cited response.
- *Case 2 (medium)*: render a shape-aware clarification phrased as a
  question proposing the specific query; persist a PendingClarification;
  do not query.
- *Case 3 (low / parse failure)*: render the generic UnclearMirrorIntent
  clarification; do not query.

Resolution-ambiguity routing per D139: title-ambiguous case or data
point references route through D134's PendingClarification with the
candidate list and ``cited_artefacts`` populated; the operator's
positional reply selects the candidate and the query proceeds.

Drill-down resolution per D141: relative intents (DrillDownToChild,
ShowParent, ShowSiblings) resolve against the conversation's current
focus, extracted from the prior mirror-conversation outbound's
``cell_payload`` column. When no prior mirror outbound exists (first
mirror turn or first turn after a cross-cell exchange that broke the
focus chain), the cell routes through D139 to D134 clarification with
a no-prior-focus phrasing.

A ``turn`` returns a ``ConversationState`` whose payload carries:
``mirror_response`` (the structured ``MirrorConversationResponse``);
``response_text`` (the rendered string for the channel adapter);
``cell_payload`` (the JSONB-shaped payload the outbound message
persists per D141); ``intent_class`` and ``confidence_band`` for
observability.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID, uuid4

from contexts.audit.domain.ports import AuditPort

from contexts.messaging.api import (
    PendingClarification,
    PendingClarificationReader,
    PendingClarificationRepository,
    create_pending_clarification,
    expire_pending_clarification,
    resolve_pending_clarification,
)

from contexts.mirror_conversation.application.ports.mirror_portfolio_reader import (  # noqa: E501
    MirrorCaseDetail,
    MirrorCaseSummary,
    MirrorDataPoint,
    MirrorDataPointSummary,
    MirrorPortfolioReader,
)
from contexts.mirror_conversation.application.response import (
    MirrorConversationResponse,
    extract_focus_from_cell_payload,
    serialise_focus_to_cell_payload,
)
from contexts.mirror_conversation.domain.intent import (
    DrillDownToChild,
    ListCases,
    MirrorIntent,
    MirrorIntentType,
    ShowCase,
    ShowDataPoint,
    ShowParent,
    ShowSiblings,
    UnclearMirrorIntent,
    is_relative,
    mirror_intent_type_of,
    parse_mirror_intent,
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
from shared_kernel.intent_classification_mirror import (
    MIRROR_INTENT_EXTRACTION_SCHEMA,
    build_mirror_extraction_prompt,
)


_PURPOSE = "mirror_query"
_RESOLUTION_CANDIDATES_KEY = "resolution_candidates"

_CONFIRMING_REPLIES = frozenset(
    {"yes", "y", "confirm", "confirmed", "ok", "okay", "sure", "go ahead"}
)
_CORRECTING_REPLIES = frozenset(
    {"no", "n", "nope", "cancel", "stop", "wait", "actually"}
)

_REFERENCE_STOPWORDS = frozenset(
    {
        "the", "a", "an", "my", "our", "this", "that", "these", "those",
        "to", "of", "for", "in", "on", "and", "or", "with", "about",
        "case", "cases", "data", "point", "points", "show", "tell",
        "me", "us",
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
    """Parse a bare positive integer reply ('1', '2') to a 1-based index."""
    normalised = _normalise(text)
    if not normalised:
        return None
    try:
        value = int(normalised)
    except ValueError:
        return None
    return value if value > 0 else None


def _significant_tokens(text: str) -> frozenset[str]:
    """Lowercase, split on non-alphanumerics, drop common reference stopwords."""
    return frozenset(
        word
        for word in re.split(r"[^a-z0-9]+", text.lower())
        if word and word not in _REFERENCE_STOPWORDS
    )


def _resolve_reference(
    reference: str,
    candidates_with_labels: tuple[tuple[str, Any], ...],
) -> tuple[Any | None, tuple[Any, ...]]:
    """Resolve a natural-language reference against ``(label, value)`` pairs.

    Returns ``(matched_value, ())`` on exactly-one match;
    ``(None, candidate_values)`` on multi-match; ``(None, ())`` on
    no-match. The matching prefers exact significant-token-set match;
    falls through to overlap scoring with ties surfacing as
    multi-match.
    """
    ref_tokens = _significant_tokens(reference)
    if not ref_tokens or not candidates_with_labels:
        return None, ()
    exact = [
        value for label, value in candidates_with_labels
        if _significant_tokens(label) == ref_tokens
    ]
    if len(exact) == 1:
        return exact[0], ()
    if len(exact) > 1:
        return None, tuple(exact)
    scored = [
        (len(ref_tokens & _significant_tokens(label)), value)
        for label, value in candidates_with_labels
    ]
    best_score = max(score for score, _ in scored)
    if best_score == 0:
        return None, ()
    winners = tuple(value for score, value in scored if score == best_score)
    if len(winners) == 1:
        return winners[0], ()
    return None, winners


class MirrorConversationCell:
    """The mirror-conversation ConversationFlow implementer (D138, D141, S52)."""

    def __init__(
        self,
        *,
        structured_output_port: StructuredOutputPort,
        mirror_portfolio_reader: MirrorPortfolioReader,
        actor: ActorContext,
        confidence_calculator: ConfidenceCalculator,
        threshold_resolver: ThresholdResolver,
        pending_clarification_reader: PendingClarificationReader,
        pending_clarification_repository: PendingClarificationRepository,
        audit_port: AuditPort,
        prior_focus: ArtefactCitation | None = None,
        originating_channel: str = "WHATSAPP",
        originating_intake_id: UUID | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._structured_output = structured_output_port
        self._reader = mirror_portfolio_reader
        self._actor = actor
        self._confidence = confidence_calculator
        self._thresholds = threshold_resolver
        self._pending_reader = pending_clarification_reader
        self._pending_repo = pending_clarification_repository
        self._audit_port = audit_port
        # D141: the cell receives prior_focus at construction time from
        # the caller (the wiring loads it from the prior mirror outbound's
        # cell_payload column). When None, relative intents route through
        # D139 to D134 clarification.
        self._prior_focus = prior_focus
        self._originating_channel = originating_channel
        self._originating_intake_id = originating_intake_id
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

        # Active-pending check first (D134 / D139 multi-turn resolution).
        active = await self._pending_reader.get_active(
            tenant_id=self._actor.tenant_context.tenant_id,
            user_id=self._actor.actor_id,
        )

        if active is not None and active.target_cell == "mirror_conversation":
            candidates = active.proposed_intent.get(
                _RESOLUTION_CANDIDATES_KEY
            )
            if candidates:
                selection = _parse_positional_selection(raw_text)
                if (
                    selection is not None
                    and 1 <= selection <= len(candidates)
                ):
                    chosen = candidates[selection - 1]
                    return await self._handle_resolution_selection(
                        state=state, active=active, chosen=chosen
                    )

            classification = _classify_reply(raw_text)
            if classification == "confirm":
                return await self._handle_pending_confirm(
                    state=state, active=active
                )
            if classification == "cancel":
                await expire_pending_clarification(
                    repository=self._pending_repo,
                    audit_port=self._audit_port,
                    actor=self._actor,
                    pending=active,
                    now=self._clock(),
                )
                response = MirrorConversationResponse(
                    text="OK, cancelled. Send a new query when ready."
                )
                return self._render_turn_state(
                    state=state,
                    response=response,
                    intent_class="",
                    confidence_band="cancelled_pending",
                )
            await expire_pending_clarification(
                repository=self._pending_repo,
                audit_port=self._audit_port,
                actor=self._actor,
                pending=active,
                now=self._clock(),
            )

        # Fresh turn: classify intent.
        try:
            intent, confidence = await self._extract_intent(raw_text)
        except StructuredOutputParseFailure:
            response = MirrorConversationResponse(
                text=(
                    "I could not interpret that as a mirror query. Try "
                    "asking me to show a case, list cases, or show a "
                    "data point."
                ),
            )
            return self._render_turn_state(
                state=state,
                response=response,
                intent_class="",
                confidence_band="parse_failure",
            )

        thresholds = self._thresholds.resolve(operation_class="mirror_query")
        band = self._classify_confidence(confidence, thresholds)

        if band == "low" or isinstance(intent, UnclearMirrorIntent):
            return await self._handle_unclear(state=state, intent=intent)

        if band == "medium":
            return await self._handle_medium_confidence(
                state=state, intent=intent
            )

        return await self._handle_high_confidence(
            state=state, intent=intent
        )

    # ---------------------------------------------------------- intent extract
    async def _extract_intent(
        self, message: str
    ) -> tuple[MirrorIntent, float]:
        request = StructuredOutputRequest(
            prompt=build_mirror_extraction_prompt(message),
            schema=MIRROR_INTENT_EXTRACTION_SCHEMA,
            latency_tier=LatencyTier.REAL_TIME_REQUIRED,
            temperature=0.0,
        )
        result = await self._structured_output.generate_structured(request)
        intent = parse_mirror_intent(result.value)
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
        self,
        *,
        state: ConversationState,
        intent: MirrorIntent,
    ) -> ConversationState:
        # Relative intents need a prior focus; route to clarification if absent.
        if is_relative(intent) and self._prior_focus is None:
            response = MirrorConversationResponse(
                text=(
                    "I don't have a recent case or data point to refer "
                    "back to. Try naming the case or data point you mean."
                ),
            )
            return self._render_turn_state(
                state=state,
                response=response,
                intent_class=mirror_intent_type_of(intent),
                confidence_band="no_prior_focus",
            )

        if isinstance(intent, ListCases):
            return await self._handle_list_cases(state=state)
        if isinstance(intent, ShowCase):
            return await self._handle_show_case(state=state, intent=intent)
        if isinstance(intent, ShowDataPoint):
            return await self._handle_show_data_point(
                state=state, intent=intent
            )
        if isinstance(intent, DrillDownToChild):
            return await self._handle_drill_down(state=state, intent=intent)
        if isinstance(intent, ShowParent):
            return await self._handle_show_parent(state=state)
        if isinstance(intent, ShowSiblings):
            return await self._handle_show_siblings(state=state)
        return await self._handle_unclear(state=state, intent=intent)

    # ----------------------------------------------------- list cases
    async def _handle_list_cases(
        self, *, state: ConversationState
    ) -> ConversationState:
        cases = await self._reader.list_cases(actor=self._actor)
        if not cases:
            response = MirrorConversationResponse(
                text="You don't have any cases yet."
            )
            return self._render_turn_state(
                state=state,
                response=response,
                intent_class=MirrorIntentType.LIST_CASES.value,
                confidence_band="high",
            )
        lines = [f"You have {len(cases)} case(s):"]
        for case in cases:
            lines.append(
                f"- {case.title} ({case.case_status}, "
                f"{case.data_point_count} data point(s))"
            )
        text = "\n".join(lines)
        cited = tuple(
            ArtefactCitation(artefact_id=c.case_id, artefact_type="case")
            for c in cases
        )
        # ListCases responses do not anchor a single focus (the operator's
        # next turn is more likely a fresh ShowCase than a relative
        # drill-down without first picking one). Leave focus None.
        response = MirrorConversationResponse(
            text=text, cited_artefacts=cited
        )
        return self._render_turn_state(
            state=state,
            response=response,
            intent_class=MirrorIntentType.LIST_CASES.value,
            confidence_band="high",
        )

    # ----------------------------------------------------- show case
    async def _handle_show_case(
        self, *, state: ConversationState, intent: ShowCase
    ) -> ConversationState:
        cases = await self._reader.find_cases(actor=self._actor)
        matched, candidates = _resolve_reference(
            intent.case_reference,
            tuple((c.title, c) for c in cases),
        )

        if matched is None and candidates:
            return await self._dispatch_resolution_ambiguity(
                state=state,
                intent=intent,
                candidates_as_artefacts=tuple(
                    ArtefactCitation(
                        artefact_id=c.case_id, artefact_type="case"
                    )
                    for c in candidates
                ),
                candidates_for_pending=[
                    {"id": str(c.case_id), "label": c.title}
                    for c in candidates
                ],
                reference=intent.case_reference,
                noun="case",
            )

        if matched is None:
            response = MirrorConversationResponse(
                text=(
                    f"I could not find a case matching "
                    f"“{intent.case_reference}”."
                ),
            )
            return self._render_turn_state(
                state=state,
                response=response,
                intent_class=MirrorIntentType.SHOW_CASE.value,
                confidence_band="resolution_no_match",
            )

        detail = await self._reader.get_case_detail(
            actor=self._actor, case_id=matched.case_id
        )
        if detail is None:
            response = MirrorConversationResponse(
                text=(
                    f"I could not load the details for "
                    f"“{matched.title}”."
                ),
            )
            return self._render_turn_state(
                state=state,
                response=response,
                intent_class=MirrorIntentType.SHOW_CASE.value,
                confidence_band="load_failed",
            )

        return self._compose_case_detail_response(
            state=state, detail=detail, intent_class=MirrorIntentType.SHOW_CASE.value
        )

    # ----------------------------------------------------- show data point
    async def _handle_show_data_point(
        self, *, state: ConversationState, intent: ShowDataPoint
    ) -> ConversationState:
        # The cell scopes the data-point search by case reference when
        # the operator provides one; otherwise scans every case's
        # data points (Phase 2-A dogfooding scale tolerates this).
        cases = await self._reader.find_cases(actor=self._actor)
        if intent.case_reference:
            case_matched, _ = _resolve_reference(
                intent.case_reference,
                tuple((c.title, c) for c in cases),
            )
            scope_cases = (case_matched,) if case_matched else ()
        else:
            scope_cases = cases

        if not scope_cases:
            response = MirrorConversationResponse(
                text=(
                    "I couldn't find a case to look in for "
                    f"“{intent.data_point_reference}”."
                ),
            )
            return self._render_turn_state(
                state=state,
                response=response,
                intent_class=MirrorIntentType.SHOW_DATA_POINT.value,
                confidence_band="no_case_scope",
            )

        all_dps: list[tuple[str, MirrorDataPointSummary]] = []
        for case in scope_cases:
            detail = await self._reader.get_case_detail(
                actor=self._actor, case_id=case.case_id
            )
            if detail is None:
                continue
            for dp in detail.data_points:
                all_dps.append((dp.label, dp))

        matched, candidates = _resolve_reference(
            intent.data_point_reference, tuple(all_dps)
        )

        if matched is None and candidates:
            return await self._dispatch_resolution_ambiguity(
                state=state,
                intent=intent,
                candidates_as_artefacts=tuple(
                    ArtefactCitation(
                        artefact_id=c.data_point_id,
                        artefact_type="data_point",
                    )
                    for c in candidates
                ),
                candidates_for_pending=[
                    {"id": str(c.data_point_id), "label": c.label}
                    for c in candidates
                ],
                reference=intent.data_point_reference,
                noun="data point",
            )

        if matched is None:
            response = MirrorConversationResponse(
                text=(
                    f"I could not find a data point matching "
                    f"“{intent.data_point_reference}”."
                ),
            )
            return self._render_turn_state(
                state=state,
                response=response,
                intent_class=MirrorIntentType.SHOW_DATA_POINT.value,
                confidence_band="resolution_no_match",
            )

        return await self._compose_data_point_response(
            state=state,
            data_point_id=matched.data_point_id,
            intent_class=MirrorIntentType.SHOW_DATA_POINT.value,
        )

    # ----------------------------------------------------- drill-down
    async def _handle_drill_down(
        self, *, state: ConversationState, intent: DrillDownToChild
    ) -> ConversationState:
        focus = self._prior_focus
        if focus is None or focus.artefact_type != "case":
            # Drill-down only makes sense from a case focus (P14 scope);
            # mid-data-point drill-down is a P15+ surface concern.
            response = MirrorConversationResponse(
                text=(
                    "I don't have a case in context to drill into. Try "
                    "asking 'show me the Q3 review' first."
                ),
            )
            return self._render_turn_state(
                state=state,
                response=response,
                intent_class=MirrorIntentType.DRILL_DOWN_TO_CHILD.value,
                confidence_band="no_drill_target",
            )

        detail = await self._reader.get_case_detail(
            actor=self._actor, case_id=focus.artefact_id
        )
        if detail is None or not detail.data_points:
            response = MirrorConversationResponse(
                text=(
                    "That case doesn't have any data points to drill "
                    "into yet."
                ),
            )
            return self._render_turn_state(
                state=state,
                response=response,
                intent_class=MirrorIntentType.DRILL_DOWN_TO_CHILD.value,
                confidence_band="no_children",
            )

        matched, candidates = _resolve_reference(
            intent.child_reference,
            tuple((dp.label, dp) for dp in detail.data_points),
        )

        if matched is None and candidates:
            return await self._dispatch_resolution_ambiguity(
                state=state,
                intent=intent,
                candidates_as_artefacts=tuple(
                    ArtefactCitation(
                        artefact_id=c.data_point_id,
                        artefact_type="data_point",
                    )
                    for c in candidates
                ),
                candidates_for_pending=[
                    {"id": str(c.data_point_id), "label": c.label}
                    for c in candidates
                ],
                reference=intent.child_reference,
                noun="data point",
            )

        if matched is None:
            response = MirrorConversationResponse(
                text=(
                    f"I couldn't find a child matching "
                    f"“{intent.child_reference}” in "
                    f"“{detail.case.title}”."
                ),
            )
            return self._render_turn_state(
                state=state,
                response=response,
                intent_class=MirrorIntentType.DRILL_DOWN_TO_CHILD.value,
                confidence_band="resolution_no_match",
            )

        return await self._compose_data_point_response(
            state=state,
            data_point_id=matched.data_point_id,
            intent_class=MirrorIntentType.DRILL_DOWN_TO_CHILD.value,
        )

    # ----------------------------------------------------- show parent
    async def _handle_show_parent(
        self, *, state: ConversationState
    ) -> ConversationState:
        focus = self._prior_focus
        if focus is None or focus.artefact_type != "data_point":
            response = MirrorConversationResponse(
                text=(
                    "I don't have a child artefact in context — there's "
                    "no parent to show. Try showing a data point first."
                ),
            )
            return self._render_turn_state(
                state=state,
                response=response,
                intent_class=MirrorIntentType.SHOW_PARENT.value,
                confidence_band="no_parent_context",
            )
        data_point = await self._reader.get_data_point(
            actor=self._actor, data_point_id=focus.artefact_id
        )
        if data_point is None:
            response = MirrorConversationResponse(
                text="I couldn't load the parent of that data point.",
            )
            return self._render_turn_state(
                state=state,
                response=response,
                intent_class=MirrorIntentType.SHOW_PARENT.value,
                confidence_band="load_failed",
            )
        detail = await self._reader.get_case_detail(
            actor=self._actor, case_id=data_point.case_id
        )
        if detail is None:
            response = MirrorConversationResponse(
                text="I couldn't load the parent case for that data point.",
            )
            return self._render_turn_state(
                state=state,
                response=response,
                intent_class=MirrorIntentType.SHOW_PARENT.value,
                confidence_band="load_failed",
            )
        return self._compose_case_detail_response(
            state=state,
            detail=detail,
            intent_class=MirrorIntentType.SHOW_PARENT.value,
        )

    # ----------------------------------------------------- show siblings
    async def _handle_show_siblings(
        self, *, state: ConversationState
    ) -> ConversationState:
        focus = self._prior_focus
        if focus is None or focus.artefact_type != "data_point":
            response = MirrorConversationResponse(
                text=(
                    "I don't have a data point in context to find "
                    "siblings of."
                ),
            )
            return self._render_turn_state(
                state=state,
                response=response,
                intent_class=MirrorIntentType.SHOW_SIBLINGS.value,
                confidence_band="no_sibling_context",
            )
        data_point = await self._reader.get_data_point(
            actor=self._actor, data_point_id=focus.artefact_id
        )
        if data_point is None:
            response = MirrorConversationResponse(
                text="I couldn't load that data point to find its siblings.",
            )
            return self._render_turn_state(
                state=state,
                response=response,
                intent_class=MirrorIntentType.SHOW_SIBLINGS.value,
                confidence_band="load_failed",
            )
        detail = await self._reader.get_case_detail(
            actor=self._actor, case_id=data_point.case_id
        )
        if detail is None:
            response = MirrorConversationResponse(
                text="I couldn't load the parent case for that data point.",
            )
            return self._render_turn_state(
                state=state,
                response=response,
                intent_class=MirrorIntentType.SHOW_SIBLINGS.value,
                confidence_band="load_failed",
            )
        siblings = tuple(
            dp for dp in detail.data_points
            if dp.data_point_id != focus.artefact_id
        )
        if not siblings:
            response = MirrorConversationResponse(
                text=(
                    f"This data point has no siblings in "
                    f"“{detail.case.title}”."
                ),
                current_focus_artefact=focus,
            )
            return self._render_turn_state(
                state=state,
                response=response,
                intent_class=MirrorIntentType.SHOW_SIBLINGS.value,
                confidence_band="high",
            )
        lines = [
            f"Siblings of this data point in “{detail.case.title}”:"
        ]
        for s in siblings:
            lines.append(f"- {s.label} ({s.data_point_type})")
        cited = tuple(
            ArtefactCitation(
                artefact_id=s.data_point_id, artefact_type="data_point"
            )
            for s in siblings
        )
        response = MirrorConversationResponse(
            text="\n".join(lines),
            cited_artefacts=cited,
            current_focus_artefact=focus,
        )
        return self._render_turn_state(
            state=state,
            response=response,
            intent_class=MirrorIntentType.SHOW_SIBLINGS.value,
            confidence_band="high",
        )

    # ----------------------------------------------------- compose helpers
    def _compose_case_detail_response(
        self,
        *,
        state: ConversationState,
        detail: MirrorCaseDetail,
        intent_class: str,
    ) -> ConversationState:
        lines = [
            f"{detail.case.title} ({detail.case.case_status})",
        ]
        if detail.data_points:
            lines.append(
                f"  {len(detail.data_points)} data point(s):"
            )
            for dp in detail.data_points:
                lines.append(f"  - {dp.label} ({dp.data_point_type})")
        else:
            lines.append("  no data points yet")
        cited: list[ArtefactCitation] = [
            ArtefactCitation(
                artefact_id=detail.case.case_id, artefact_type="case"
            )
        ]
        for dp in detail.data_points:
            cited.append(
                ArtefactCitation(
                    artefact_id=dp.data_point_id,
                    artefact_type="data_point",
                )
            )
        focus = ArtefactCitation(
            artefact_id=detail.case.case_id, artefact_type="case"
        )
        response = MirrorConversationResponse(
            text="\n".join(lines),
            cited_artefacts=tuple(cited),
            current_focus_artefact=focus,
        )
        return self._render_turn_state(
            state=state,
            response=response,
            intent_class=intent_class,
            confidence_band="high",
        )

    async def _compose_data_point_response(
        self,
        *,
        state: ConversationState,
        data_point_id: UUID,
        intent_class: str,
    ) -> ConversationState:
        dp = await self._reader.get_data_point(
            actor=self._actor, data_point_id=data_point_id
        )
        if dp is None:
            response = MirrorConversationResponse(
                text="I could not load that data point.",
            )
            return self._render_turn_state(
                state=state,
                response=response,
                intent_class=intent_class,
                confidence_band="load_failed",
            )
        value_text = dp.current_value.get("text") or str(dp.current_value)
        text = (
            f"Data point ({dp.data_point_type}):\n"
            f"  {value_text}\n"
            f"  {dp.revision_count} revision(s)."
        )
        focus = ArtefactCitation(
            artefact_id=dp.data_point_id, artefact_type="data_point"
        )
        response = MirrorConversationResponse(
            text=text,
            cited_artefacts=(focus,),
            current_focus_artefact=focus,
        )
        return self._render_turn_state(
            state=state,
            response=response,
            intent_class=intent_class,
            confidence_band="high",
        )

    # ----------------------------------------------------- dispatch medium
    async def _handle_medium_confidence(
        self,
        *,
        state: ConversationState,
        intent: MirrorIntent,
    ) -> ConversationState:
        summary = _summarise_intent(intent)
        text = (
            f"It sounds like you want me to {summary}. "
            "Confirm with 'yes' or correct me with 'no'."
        )
        await self._persist_pending(
            intent=intent,
            proposed_action_summary=f"mirror_query: {summary}",
            resolution_candidates=None,
        )
        response = MirrorConversationResponse(text=text)
        return self._render_turn_state(
            state=state,
            response=response,
            intent_class=mirror_intent_type_of(intent),
            confidence_band="medium",
        )

    # ----------------------------------------------------- dispatch unclear
    async def _handle_unclear(
        self,
        *,
        state: ConversationState,
        intent: MirrorIntent,
    ) -> ConversationState:
        clarification = (
            intent.clarification
            if isinstance(intent, UnclearMirrorIntent)
            else (
                "I'm not sure what you'd like to see. Try asking to "
                "list cases, show a case, or show a data point."
            )
        )
        response = MirrorConversationResponse(text=clarification)
        return self._render_turn_state(
            state=state,
            response=response,
            intent_class=MirrorIntentType.UNCLEAR_MIRROR.value,
            confidence_band="low",
        )

    # --------------------------------------------------- resolution-ambig
    async def _dispatch_resolution_ambiguity(
        self,
        *,
        state: ConversationState,
        intent: MirrorIntent,
        candidates_as_artefacts: tuple[ArtefactCitation, ...],
        candidates_for_pending: list[dict[str, str]],
        reference: str,
        noun: str,
    ) -> ConversationState:
        numbered = [
            f"{idx + 1}. {c['label']}"
            for idx, c in enumerate(candidates_for_pending)
        ]
        text = (
            f"I found {len(candidates_for_pending)} {noun}s matching "
            f"“{reference}”. Which did you mean? Reply with a "
            "number.\n" + "\n".join(numbered)
        )
        await self._persist_pending(
            intent=intent,
            proposed_action_summary=(
                f"choose among {len(candidates_for_pending)} {noun}s "
                f"matching “{reference}”"
            ),
            resolution_candidates=candidates_for_pending,
        )
        response = MirrorConversationResponse(
            text=text,
            cited_artefacts=candidates_as_artefacts,
        )
        return self._render_turn_state(
            state=state,
            response=response,
            intent_class=mirror_intent_type_of(intent),
            confidence_band="resolution_ambiguous",
        )

    async def _handle_resolution_selection(
        self,
        *,
        state: ConversationState,
        active: PendingClarification,
        chosen: dict[str, Any],
    ) -> ConversationState:
        chosen_id = UUID(chosen["id"])
        intent = _intent_from_pending(active)

        await resolve_pending_clarification(
            repository=self._pending_repo,
            audit_port=self._audit_port,
            actor=self._actor,
            pending=active,
            resolution="confirmed",
        )

        # The pending intent determines whether the selection is a case or
        # a data point; we re-dispatch the chosen id through the right
        # response composer.
        if isinstance(intent, ShowCase):
            detail = await self._reader.get_case_detail(
                actor=self._actor, case_id=chosen_id
            )
            if detail is None:
                return self._render_turn_state(
                    state=state,
                    response=MirrorConversationResponse(
                        text="I couldn't load the selected case."
                    ),
                    intent_class=MirrorIntentType.SHOW_CASE.value,
                    confidence_band="load_failed",
                )
            return self._compose_case_detail_response(
                state=state,
                detail=detail,
                intent_class=MirrorIntentType.SHOW_CASE.value,
            )
        # Default: treat the selection as a data point id.
        return await self._compose_data_point_response(
            state=state,
            data_point_id=chosen_id,
            intent_class=mirror_intent_type_of(intent),
        )

    async def _handle_pending_confirm(
        self,
        *,
        state: ConversationState,
        active: PendingClarification,
    ) -> ConversationState:
        intent = _intent_from_pending(active)
        await resolve_pending_clarification(
            repository=self._pending_repo,
            audit_port=self._audit_port,
            actor=self._actor,
            pending=active,
            resolution="confirmed",
        )
        return await self._handle_high_confidence(
            state=state, intent=intent
        )

    # ----------------------------------------------------- persist pending
    async def _persist_pending(
        self,
        *,
        intent: MirrorIntent,
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
            target_cell="mirror_conversation",
        )

    # ----------------------------------------------------- render helper
    def _render_turn_state(
        self,
        *,
        state: ConversationState,
        response: MirrorConversationResponse,
        intent_class: str,
        confidence_band: str,
    ) -> ConversationState:
        # D141: derive the per-implementer cell_payload from the
        # response's current_focus_artefact for the wiring layer to
        # persist on the outbound Message row.
        cell_payload = (
            serialise_focus_to_cell_payload(response.current_focus_artefact)
            if response.current_focus_artefact is not None
            else None
        )
        return ConversationState(
            conversation_id=state.conversation_id,
            purpose=state.purpose,
            turn_count=state.turn_count + 1,
            is_open=True,
            payload={
                "mirror_response": response,
                "response_text": response.text,
                "cell_payload": cell_payload,
                "intent_class": intent_class,
                "confidence_band": confidence_band,
            },
        )


# ---------------------------------------------------------------- helpers


def _summarise_intent(intent: MirrorIntent) -> str:
    if isinstance(intent, ShowCase):
        return f"show the case “{intent.case_reference}”"
    if isinstance(intent, ListCases):
        return "list your cases"
    if isinstance(intent, ShowDataPoint):
        scope = (
            f" on case “{intent.case_reference}”"
            if intent.case_reference
            else ""
        )
        return (
            f"show the data point “{intent.data_point_reference}”"
            f"{scope}"
        )
    if isinstance(intent, DrillDownToChild):
        return f"drill into “{intent.child_reference}”"
    if isinstance(intent, ShowParent):
        return "show the parent of the current data point"
    if isinstance(intent, ShowSiblings):
        return "show the siblings of the current data point"
    return "clarify your request"


def _intent_to_dict(intent: MirrorIntent) -> dict[str, Any]:
    base = {
        "intent_class": mirror_intent_type_of(intent),
        "purpose": _PURPOSE,
    }
    if isinstance(intent, ShowCase):
        return {**base, "case_reference": intent.case_reference}
    if isinstance(intent, ListCases):
        return base
    if isinstance(intent, ShowDataPoint):
        return {
            **base,
            "data_point_reference": intent.data_point_reference,
            "case_reference": intent.case_reference,
        }
    if isinstance(intent, DrillDownToChild):
        return {**base, "child_reference": intent.child_reference}
    if isinstance(intent, ShowParent):
        return base
    if isinstance(intent, ShowSiblings):
        return base
    return base


def _intent_from_pending(active: PendingClarification) -> MirrorIntent:
    raw = dict(active.proposed_intent)
    raw.pop(_RESOLUTION_CANDIDATES_KEY, None)
    raw.pop("purpose", None)
    return parse_mirror_intent(raw)


__all__ = ["MirrorConversationCell"]
