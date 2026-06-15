"""CheckinCell — the pending-only check-in ConversationFlow implementer (D192, D194, S97b).

A two-stage cell carried across two inbound turns via the
``PendingClarification.proposed_intent`` stage field (the D141 mechanism the
mirror cell already uses):

- **awaiting_report** (the composer's pending): parse the free-text reply
  against the eligible levers, build the lever-aware confirm echo, and
  transition the pending to ``awaiting_confirm`` carrying the parsed outcomes.
- **awaiting_confirm**: on confirm, write the three-state outcomes (idempotent
  by beat day) and resolve; on a correction, re-parse and merge over the prior
  parse, then re-echo; on cancel, expire the pending and write nothing.

The cell is **pending-only** (D194): it is reached solely by the active-pending
path (D140), never the meta-classifier. Cross-context work (the parse, the
two-store write) is behind consumer ports; the pending machinery is the
messaging context's public API (the legal D17 seam, as audit/mirror cells use).

Application code; no framework imports beyond shared_kernel + messaging.api.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Callable
from uuid import UUID, uuid4

from shared_kernel import ActorContext
from shared_kernel.conversation_flow import (
    ConversationClosure,
    ConversationInput,
    ConversationInvocation,
    ConversationOutcome,
    ConversationState,
)

from contexts.audit.domain.ports import AuditPort
from contexts.messaging.api import (
    PendingClarification,
    PendingClarificationReader,
    PendingClarificationRepository,
    create_pending_clarification,
    expire_pending_clarification,
    resolve_pending_clarification,
)

from contexts.checkin.application.ports.checkin_writer import (
    CheckinWriteResult,
    CheckinWriter,
)
from contexts.checkin.application.ports.reply_parser import CheckinReplyParser
from contexts.checkin.domain.confirm_echo import build_confirm_echo
from contexts.checkin.domain.lever import EligibleLever
from contexts.checkin.domain.outcome import ParsedLeverOutcome

_PURPOSE = "daily_checkin"
_TARGET_CELL = "checkin"
_STAGE_REPORT = "awaiting_report"
_STAGE_CONFIRM = "awaiting_confirm"
_REPLY_KEY = "checkin_reply"

_CONFIRM_WORDS = {
    "yes", "y", "yep", "yeah", "yup", "confirm", "confirmed", "correct",
    "right", "ok", "okay", "done", "all done", "looks right", "sounds right",
    "👍", "👍🏽",
}
_CANCEL_WORDS = {
    "cancel", "stop", "nvm", "nevermind", "never mind", "forget it", "skip",
}


def _classify_confirm(text: str) -> str:
    """Classify an awaiting_confirm reply as confirm / cancel / other.

    Lexical and deliberately narrow; an unmatched reply is treated as a
    *correction* (re-parsed), never a silent confirm. Wording is build-altitude
    and feel-checked on the live round-trip."""
    t = text.strip().lower().strip("!.?")
    if t in _CONFIRM_WORDS:
        return "confirm"
    if t in _CANCEL_WORDS:
        return "cancel"
    return "other"


def _merge_outcomes(
    prior: tuple[ParsedLeverOutcome, ...],
    correction: tuple[ParsedLeverOutcome, ...],
) -> tuple[ParsedLeverOutcome, ...]:
    """Override prior outcomes by the correction's, keyed on commitment id."""
    by_id: dict[UUID, ParsedLeverOutcome] = {p.commitment_id: p for p in prior}
    for c in correction:
        by_id[c.commitment_id] = c
    return tuple(by_id.values())


class CheckinCell:
    """The daily three-state check-in cell (ConversationFlow, structural)."""

    def __init__(
        self,
        *,
        reply_parser: CheckinReplyParser,
        checkin_writer: CheckinWriter,
        pending_clarification_reader: PendingClarificationReader,
        pending_clarification_repository: PendingClarificationRepository,
        audit_port: AuditPort,
        actor: ActorContext,
        originating_channel: str = "WHATSAPP",
        originating_intake_id: UUID | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._parser = reply_parser
        self._writer = checkin_writer
        self._pending_reader = pending_clarification_reader
        self._pending_repo = pending_clarification_repository
        self._audit_port = audit_port
        self._actor = actor
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
        active = await self._pending_reader.get_active(
            tenant_id=self._actor.tenant_context.tenant_id,
            user_id=self._actor.actor_id,
        )
        if active is None or active.target_cell != _TARGET_CELL:
            return self._reply(
                state, "No check-in is awaiting a reply right now."
            )

        stage = active.proposed_intent.get("stage", _STAGE_REPORT)
        if stage == _STAGE_CONFIRM:
            return await self._handle_confirm_stage(
                state, active, user_input.text
            )
        return await self._handle_report_stage(state, active, user_input.text)

    # --------------------------------------------------------- report stage
    async def _handle_report_stage(
        self,
        state: ConversationState,
        active: PendingClarification,
        text: str,
    ) -> ConversationState:
        levers = _levers_from(active)
        parsed = await self._parser.parse(
            reply_text=text, levers=levers, actor=self._actor
        )
        if not parsed:
            return self._reply(
                state,
                "I didn't catch which ones — reply like "
                "“did Litany and Voice, missed Stretch”.",
            )
        return await self._echo_and_await_confirm(
            state=state, active=active, levers=levers, parsed=parsed
        )

    # -------------------------------------------------------- confirm stage
    async def _handle_confirm_stage(
        self,
        state: ConversationState,
        active: PendingClarification,
        text: str,
    ) -> ConversationState:
        decision = _classify_confirm(text)

        if decision == "cancel":
            await expire_pending_clarification(
                repository=self._pending_repo,
                audit_port=self._audit_port,
                actor=self._actor,
                pending=active,
                now=self._clock(),
            )
            return self._reply(state, "OK — nothing logged.")

        if decision == "confirm":
            parsed = tuple(
                ParsedLeverOutcome.from_dict(d)
                for d in active.proposed_intent.get("parsed", [])
            )
            beat_date = date.fromisoformat(active.proposed_intent["beat_date"])
            result = await self._writer.write_outcomes(
                actor=self._actor, outcomes=parsed, beat_date=beat_date
            )
            await resolve_pending_clarification(
                repository=self._pending_repo,
                audit_port=self._audit_port,
                actor=self._actor,
                pending=active,
                resolution="checkin confirmed and written",
            )
            return self._reply(state, _confirmation_text(result))

        # A correction — re-parse and merge over the prior parse, then re-echo.
        levers = _levers_from(active)
        correction = await self._parser.parse(
            reply_text=text, levers=levers, actor=self._actor
        )
        if not correction:
            return self._reply(
                state,
                "Reply yes to confirm, or tell me which you missed "
                "(e.g. “missed Stretch”).",
            )
        prior = tuple(
            ParsedLeverOutcome.from_dict(d)
            for d in active.proposed_intent.get("parsed", [])
        )
        merged = _merge_outcomes(prior, correction)
        return await self._echo_and_await_confirm(
            state=state, active=active, levers=levers, parsed=merged
        )

    # ------------------------------------------------------------- helpers
    async def _echo_and_await_confirm(
        self,
        *,
        state: ConversationState,
        active: PendingClarification,
        levers: tuple[EligibleLever, ...],
        parsed: tuple[ParsedLeverOutcome, ...],
    ) -> ConversationState:
        echo = build_confirm_echo(levers=levers, parsed=parsed)
        new_intent = {
            "stage": _STAGE_CONFIRM,
            "beat_date": active.proposed_intent["beat_date"],
            "levers": [lever.to_dict() for lever in levers],
            "parsed": [outcome.to_dict() for outcome in parsed],
        }
        # create_pending_clarification expires the prior PENDING before
        # inserting, holding the one-PENDING-per-user invariant (D134).
        await create_pending_clarification(
            repository=self._pending_repo,
            audit_port=self._audit_port,
            actor=self._actor,
            user_id=self._actor.actor_id,
            originating_channel=active.originating_channel,
            originating_user_address=active.originating_user_address,
            originating_intake_id=(
                self._originating_intake_id or active.originating_intake_id
            ),
            proposed_intent=new_intent,
            proposed_action_summary=echo,
            target_cell=_TARGET_CELL,
        )
        return self._reply(state, echo)

    def _reply(self, state: ConversationState, text: str) -> ConversationState:
        return ConversationState(
            conversation_id=state.conversation_id,
            purpose=state.purpose,
            turn_count=state.turn_count + 1,
            is_open=True,
            payload={**state.payload, _REPLY_KEY: text},
        )


def _levers_from(active: PendingClarification) -> tuple[EligibleLever, ...]:
    return tuple(
        EligibleLever.from_dict(d)
        for d in active.proposed_intent.get("levers", [])
    )


def _confirmation_text(result: CheckinWriteResult) -> str:
    bits: list[str] = []
    if result.dids_written:
        bits.append(f"{result.dids_written} done")
    if result.reported_didnts_written:
        bits.append(f"{result.reported_didnts_written} not done")
    if not bits:
        return "Already logged for today — nothing to add."
    return "Logged: " + ", ".join(bits) + "."


__all__ = ["CheckinCell"]
