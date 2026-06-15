"""Composition wiring for the check-in cell's consumer ports (D192, D194, S97b).

The legal cross-context seam (D17): ``apps/`` may import producer-context
application modules directly, so these adapters satisfy the check-in context's
consumer ports by composing daily_driver. The writer translates the check-in's
``ParsedLeverOutcome`` into daily_driver's ``log_checkin_outcomes`` use case
(the idempotent three-state write); the eligible-levers reader and the LLM reply
parser land here too as Commits 2 and 3 wire them.

Lands in its own module mirroring ``apps/api/_daily_briefing_wiring.py`` — a
per-context wiring file keeps each cross-context seam grep-able.
"""

from __future__ import annotations

import logging
from datetime import date

from shared_kernel import ActorContext
from shared_kernel.structured_output import (
    StructuredOutputParseFailure,
    StructuredOutputPort,
    StructuredOutputRequest,
)

from contexts.daily_driver.application.log_checkin_outcomes import (
    CheckinOutcomeInput,
    log_checkin_outcomes,
)
from contexts.daily_driver.ports.commitment_repository import (
    CommitmentRepository,
)

from contexts.checkin.application.ports.checkin_writer import CheckinWriteResult
from contexts.checkin.domain.lever import EligibleLever
from contexts.checkin.domain.outcome import CheckinState, ParsedLeverOutcome
from contexts.checkin.domain.reply_parse import (
    PARSE_SCHEMA,
    build_parse_prompt,
    map_parsed_outcomes,
)

_logger = logging.getLogger(__name__)


class CheckinWriterAdapter:
    """apps/ adapter implementing the check-in context's CheckinWriter port.

    Translates the parsed per-lever outcomes into daily_driver's idempotent
    three-state write (``did`` → completion, ``reported_didnt`` → checkin
    response, both guarded by an exists-by-beat-day check)."""

    def __init__(
        self, *, commitment_repository: CommitmentRepository
    ) -> None:
        self._repository = commitment_repository

    async def write_outcomes(
        self,
        *,
        actor: ActorContext,
        outcomes: tuple[ParsedLeverOutcome, ...],
        beat_date: date,
    ) -> CheckinWriteResult:
        inputs = tuple(
            CheckinOutcomeInput(
                commitment_id=outcome.commitment_id,
                did=outcome.state is CheckinState.DID,
            )
            for outcome in outcomes
        )
        counts = await log_checkin_outcomes(
            repository=self._repository,
            actor=actor,
            outcomes=inputs,
            beat_date=beat_date,
        )
        return CheckinWriteResult(
            dids_written=counts.dids_written,
            reported_didnts_written=counts.reported_didnts_written,
            skipped_idempotent=counts.skipped_idempotent,
        )


class CheckinReplyParserAdapter:
    """apps/ adapter implementing the check-in context's CheckinReplyParser port.

    Maps a free-text reply to per-lever outcomes through the provider-agnostic
    StructuredOutputPort (the inference LiteLLM adapter — the litellm SDK stays
    confined there, never in apps/ or the checkin context). The D184 pattern:
    this adapter assembles the lever context the model needs; the pure
    domain helpers build the prompt/schema and map the response, holding the
    silence-is-not-a-miss semantic."""

    def __init__(
        self, *, structured_output_port: StructuredOutputPort
    ) -> None:
        self._structured_output = structured_output_port

    async def parse(
        self,
        *,
        reply_text: str,
        levers: tuple[EligibleLever, ...],
        actor: ActorContext,
    ) -> tuple[ParsedLeverOutcome, ...]:
        if not levers or not reply_text.strip():
            return ()
        request = StructuredOutputRequest(
            prompt=build_parse_prompt(reply_text=reply_text, levers=levers),
            schema=PARSE_SCHEMA,
        )
        try:
            response = await self._structured_output.generate_structured(
                request
            )
        except StructuredOutputParseFailure:
            # An unparseable reply yields no outcomes; the cell re-prompts
            # rather than writing a guess.
            _logger.info("check-in parse produced no schema-conforming output")
            return ()
        return map_parsed_outcomes(response.value, levers)


__all__ = ["CheckinReplyParserAdapter", "CheckinWriterAdapter"]
