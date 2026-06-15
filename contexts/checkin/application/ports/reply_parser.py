"""CheckinReplyParser consumer port (D192, D184, S97b).

The free-text reply is parsed against the eligible levers into per-lever
outcomes through the provider-agnostic LLM interface (the litellm JSON-mode
adapter wired in ``apps/``). This is the D184 pattern — the use case (not a
pure domain function) assembles the lever context the extractor needs; the
parser sees the levers *grouped by goal* so a goal-level reply ("did my meds")
resolves to the right per-lever ids while an unmentioned lever produces no
entry at all ("silence is not a miss" at the parse layer).

Framework-free; stdlib-only Protocol shape.
"""

from __future__ import annotations

from typing import Protocol

from shared_kernel import ActorContext

from contexts.checkin.domain.lever import EligibleLever
from contexts.checkin.domain.outcome import ParsedLeverOutcome


class CheckinReplyParser(Protocol):
    """Map a free-text check-in reply to per-lever did/reported_didnt outcomes."""

    async def parse(
        self,
        *,
        reply_text: str,
        levers: tuple[EligibleLever, ...],
        actor: ActorContext,
    ) -> tuple[ParsedLeverOutcome, ...]:
        """Return one outcome per lever the reply spoke to.

        A lever the reply does not mention is **absent** from the result —
        never returned as a silent or reported_didnt state. The returned
        outcomes reference only ``commitment_id`` values present in ``levers``.
        """
        ...


__all__ = ["CheckinReplyParser"]
