"""Goal — the typed goal layer above commitments (D163).

A ``Goal`` is an Outcome the daily driver holds, placed on the three axes of
the whole-life goal taxonomy (D163): the *engine* and *target* collapse into a
``mode`` (homeostatic / progressive / sequence), *control* says whether the
actor's own levers determine the outcome (``SELF``) or another party determines
it and the actor only influences (``OTHER``), and the *subject* is whose goal it
is (``SELF`` or ``OTHER``). A goal's lever is a Commitment (Postgres); the goal
itself is an Outcome node in the graph, connected by a lever-to-outcome edge.

S62 instances only the progressive-cadence / control-self / subject-self shape
through German; every other value is defined here but uninstanced (D163). No
remedy logic lives here beyond the level-ladder mechanics the progressive shape
needs — the raise-or-hold recommendation is composed on the read path
(``goal_view``), and the remaining modes' remedies arrive with the session that
instances a goal of that shape.

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class GoalMode(str, Enum):
    """How the lever relates to the outcome (D163: engine × target).

    ``HOMEOSTATIC`` repeats to hold a level (behind = drift, remedy =
    re-establish). ``PROGRESSIVE`` repeats to raise a level (behind = not
    advancing, remedy = adjust the target). ``SEQUENCE`` releases tasks toward
    a terminal (behind = blocked, remedy = unblock or drop). S62 instances only
    ``PROGRESSIVE``.
    """

    HOMEOSTATIC = "homeostatic"
    PROGRESSIVE = "progressive"
    SEQUENCE = "sequence"


class ControlAxis(str, Enum):
    """Whether the actor's levers determine the outcome (D163).

    ``SELF`` — the actor's own levers determine it (a determine-goal).
    ``OTHER`` — another party determines it and the actor only influences (an
    influence-goal; the probabilistic gap, uninstanced at S62).
    """

    SELF = "self"
    OTHER = "other"


class Subject(str, Enum):
    """Whose goal it is (D163). ``OTHER`` (e.g. another person's progress) is
    schema-present but uninstanced at S62."""

    SELF = "self"
    OTHER = "other"


@dataclass(frozen=True)
class LevelLadder:
    """An ordered ladder of named levels plus the current target (D163).

    The adjustable qualitative target for a progressive goal: ``levels`` is the
    ordered ascent (lowest first), ``current_target_level`` is the level the
    goal is currently aiming at. Qualitative, not numeric — quantitative target
    inference stays deferred per D156.
    """

    levels: tuple[str, ...]
    current_target_level: str

    def __post_init__(self) -> None:
        if len(self.levels) < 2:
            raise ValueError("a level ladder needs at least two levels")
        if len(set(self.levels)) != len(self.levels):
            raise ValueError("level ladder must not repeat a level")
        if self.current_target_level not in self.levels:
            raise ValueError(
                f"current_target_level {self.current_target_level!r} is not on "
                "the ladder"
            )

    def index_of(self, level: str) -> int:
        return self.levels.index(level)

    @property
    def current_index(self) -> int:
        return self.index_of(self.current_target_level)

    @property
    def is_at_top(self) -> bool:
        return self.current_index == len(self.levels) - 1

    def level_above(self, level: str) -> str | None:
        """The level one step above ``level``, or ``None`` at the top."""
        idx = self.index_of(level)
        if idx >= len(self.levels) - 1:
            return None
        return self.levels[idx + 1]

    @property
    def next_target(self) -> str | None:
        """The level a raise would move the current target to (``None`` at top)."""
        return self.level_above(self.current_target_level)


@dataclass(frozen=True)
class Goal:
    """A typed goal (Outcome) above commitments (D163).

    ``id`` is the Outcome node id; ``lever_commitment_id`` is the Commitment
    that serves as its lever (Postgres). ``ladder`` is present for a progressive
    goal and ``None`` otherwise.
    """

    id: UUID
    tenant_id: UUID
    jurisdiction: str
    name: str
    mode: GoalMode
    control: ControlAxis
    subject: Subject
    lever_commitment_id: UUID
    ladder: LevelLadder | None = None

    def __post_init__(self) -> None:
        if not self.jurisdiction.strip():
            raise ValueError("jurisdiction must be non-empty")
        if not self.name.strip():
            raise ValueError("name must be non-empty")
        if self.mode is GoalMode.PROGRESSIVE and self.ladder is None:
            raise ValueError("a progressive goal requires a level ladder")


__all__ = ["ControlAxis", "Goal", "GoalMode", "LevelLadder", "Subject"]
