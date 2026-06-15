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

from datetime import date

from shared_kernel import ActorContext

from contexts.daily_driver.application.log_checkin_outcomes import (
    CheckinOutcomeInput,
    log_checkin_outcomes,
)
from contexts.daily_driver.ports.commitment_repository import (
    CommitmentRepository,
)

from contexts.checkin.application.ports.checkin_writer import CheckinWriteResult
from contexts.checkin.domain.outcome import CheckinState, ParsedLeverOutcome


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


__all__ = ["CheckinWriterAdapter"]
