"""EligibleLever — a daily-cadence homeostatic lever the check-in prompts for (D192, S97b).

The eligible set is discovered live (the composer's Neo4j ``mode``-join over
``:Outcome{mode:'homeostatic'}`` to its levers, kept to ``expected_interval_days
<= 1`` from Postgres — never hardcoded). Each lever carries its parent goal so
the prompt can list **goal-level** labels (keeping clinical multi-lever names —
e.g. the medication levers under "Health regimen" — off the channel) while the
parser still resolves the reply to per-lever commitment ids.

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class EligibleLever:
    """One daily-cadence homeostatic lever, carrying its parent goal."""

    commitment_id: UUID
    name: str
    goal_id: UUID
    goal_name: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("EligibleLever.name must be non-empty")
        if not self.goal_name.strip():
            raise ValueError("EligibleLever.goal_name must be non-empty")

    def to_dict(self) -> dict[str, str]:
        """Serialise for the PendingClarification.proposed_intent payload."""
        return {
            "commitment_id": str(self.commitment_id),
            "name": self.name,
            "goal_id": str(self.goal_id),
            "goal_name": self.goal_name,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "EligibleLever":
        return cls(
            commitment_id=UUID(str(raw["commitment_id"])),
            name=str(raw["name"]),
            goal_id=UUID(str(raw["goal_id"])),
            goal_name=str(raw["goal_name"]),
        )


def goal_labels(levers: tuple[EligibleLever, ...]) -> tuple[str, ...]:
    """The distinct goal labels for the prompt, in first-seen order.

    Goal-level — a multi-lever goal (Health regimen's medication levers)
    appears once, by goal name, never by its clinical lever names (D192's
    privacy-by-design message shape).
    """
    seen: list[str] = []
    for lever in levers:
        if lever.goal_name not in seen:
            seen.append(lever.goal_name)
    return tuple(seen)


__all__ = ["EligibleLever", "goal_labels"]
