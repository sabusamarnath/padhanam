"""CheckinWriter consumer port (D192, Option B, S97b).

The write splits by state and is **idempotent on (tenant, commitment, beat
day)** (Step-0 finding: the stores were not day-idempotent, so the guard lives
in the write path). A ``did`` writes one ``commitment_completions`` row stamped
to the scheduled beat day (the single did-source — never the checkin store); a
``reported_didnt`` writes one ``commitment_checkin_responses`` row with
``beat_date`` = the scheduled day and ``outcome='reported_didnt'``; silence
writes neither (it never reaches the writer — there is no outcome for it).

Day attribution uses the check-in's **scheduled beat day** carried on the
pending (the injectable-clock seam across the round-trip), not the reply's
wall-clock instant. The writer is satisfied by an ``apps/`` adapter over
daily_driver's completion + checkin-response repositories.

Framework-free; stdlib-only Protocol shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from shared_kernel import ActorContext

from contexts.checkin.domain.outcome import ParsedLeverOutcome


@dataclass(frozen=True)
class CheckinWriteResult:
    """Counts of what the write actually persisted (idempotent skips excluded)."""

    dids_written: int
    reported_didnts_written: int
    skipped_idempotent: int


class CheckinWriter(Protocol):
    """Persist the three-state outcomes, idempotent by (tenant, commitment, day)."""

    async def write_outcomes(
        self,
        *,
        actor: ActorContext,
        outcomes: tuple[ParsedLeverOutcome, ...],
        beat_date: date,
    ) -> CheckinWriteResult:
        """Write each outcome to its store, skipping any already present for the
        ``(tenant, commitment, beat_date)`` triple. Returns the persisted counts."""
        ...


__all__ = ["CheckinWriteResult", "CheckinWriter"]
