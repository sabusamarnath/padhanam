"""Check-in outcome value objects — the three states at the parse layer (D192, S97b).

Three states, never two. A ``DID`` is a completion; a ``REPORTED_DIDNT`` is a
tracked negative with evidence; **silence** is the absence of a
``ParsedLeverOutcome`` for a lever (never a ``REPORTED_DIDNT``) — "silence is
not a miss" enforced at the parse layer by an unmentioned lever producing no
entry at all.

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID


class CheckinState(str, Enum):
    """The two *reportable* states. Silence is the absence of an outcome.

    ``DID`` writes to ``commitment_completions`` (the single did-source);
    ``REPORTED_DIDNT`` writes to ``commitment_checkin_responses`` with
    ``outcome='reported_didnt'``. The values match the
    ``commitment_checkin_responses.outcome`` CHECK.
    """

    DID = "did"
    REPORTED_DIDNT = "reported_didnt"


@dataclass(frozen=True)
class ParsedLeverOutcome:
    """One lever the reply spoke to, tagged did or reported_didnt.

    An unmentioned lever has **no** ``ParsedLeverOutcome`` — it is never
    represented here as a silent or unknown state.
    """

    commitment_id: UUID
    state: CheckinState

    def to_dict(self) -> dict[str, str]:
        return {
            "commitment_id": str(self.commitment_id),
            "state": self.state.value,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ParsedLeverOutcome":
        return cls(
            commitment_id=UUID(str(raw["commitment_id"])),
            state=CheckinState(str(raw["state"])),
        )


__all__ = ["CheckinState", "ParsedLeverOutcome"]
