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


class StepState(str, Enum):
    """The state of one lever step in a sequence goal's chain (D163, S63).

    A sequence releases tasks toward a terminal: ``READY`` is the actionable
    step (all predecessors done), ``BLOCKED`` waits on a predecessor, ``DONE``
    has been completed, ``DROPPED`` was abandoned (the operator's explicit
    drop). The chain's shape — which step is active, what is blocked — is what
    the unblock-or-drop remedy reads.
    """

    READY = "ready"
    BLOCKED = "blocked"
    DONE = "done"
    DROPPED = "dropped"


class TerminalState(str, Enum):
    """The state of a sequence goal's influence-gated terminal (D163, S63).

    ``PENDING`` — the terminal has not been reached; for a control-influence
    goal this is the part another party decides (the employer's offer). Its
    richer reading (the probabilistic did-my-influence-land gap) is deferred to
    the influence instance; S63 represents it as a state only. ``REACHED`` —
    the terminal happened.
    """

    PENDING = "pending"
    REACHED = "reached"


@dataclass(frozen=True)
class LeverStep:
    """One step in a sequence goal's lever chain (D163, S63).

    ``commitment_id`` is the Postgres Commitment that serves as this step's
    lever; ``order`` is its 1-based position in the chain; ``state`` is its
    chain state. The step is a lever the actor controls — unblock-or-drop
    operates on the steps, not on the influence-gated terminal.
    """

    commitment_id: UUID
    order: int
    state: StepState

    def __post_init__(self) -> None:
        if self.order < 1:
            raise ValueError("step order is 1-based; must be >= 1")


@dataclass(frozen=True)
class Terminal:
    """A sequence goal's terminal — the goal reached once (D163, S63).

    ``target`` is the qualitative description of the goal reached once (e.g.
    "Offer accepted"); ``state`` is whether it has been reached. Unlike a
    progressive ladder, a terminal is a point, not a ratchet.
    """

    target: str
    state: TerminalState

    def __post_init__(self) -> None:
        if not self.target.strip():
            raise ValueError("terminal target must be non-empty")


@dataclass(frozen=True)
class Goal:
    """A typed goal (Outcome) above commitments (D163).

    ``id`` is the Outcome node id. A **progressive** goal has a single
    ``lever_commitment_id`` (Postgres) and a ``ladder``. A **sequence** goal has
    a ``terminal`` and an ordered chain of ``steps`` (each a lever the actor
    controls). The unused shape's fields stay at their defaults.
    """

    id: UUID
    tenant_id: UUID
    jurisdiction: str
    name: str
    mode: GoalMode
    control: ControlAxis
    subject: Subject
    lever_commitment_id: UUID | None = None
    # Multi-commitment goals (D177): a goal's work is often several distinct
    # commitments (a health regimen is four medications; a fitness goal is
    # strength, cardio, mobility). The full set of lever-commitments any mode
    # may carry; the confirmed tier matches a unit against any of them. The
    # singular ``lever_commitment_id`` stays the primary lever (the goal_view
    # progress read for progressive/homeostatic); this carries the whole set.
    lever_commitment_ids: tuple[UUID, ...] = ()
    ladder: LevelLadder | None = None
    terminal: Terminal | None = None
    steps: tuple[LeverStep, ...] = ()
    # Goal-owned alias terms — category synonyms beyond the name, matched by the
    # candidate keyword path (D174 tier two). "Fitness" links to "Strength" via
    # an alias. Category synonyms only, never per-instance referential terms.
    aliases: tuple[str, ...] = ()
    # Domain (D179): the surface tier a goal's covered work renders under
    # (work / personal / family — KNOWN_CALENDAR_DOMAINS). A calendar item whose
    # unit serves this goal inherits this domain at the Today read; an unset
    # domain (None) falls through to the connection's default tag, like an
    # orphan. Constrained to the known set; the read clamps an unknown value via
    # ``resolve_calendar_domain``. A distinct ``health`` tier is a deferred
    # surface addition (S83), so the health regimen carries ``personal`` today.
    domain: str | None = None

    def __post_init__(self) -> None:
        if not self.jurisdiction.strip():
            raise ValueError("jurisdiction must be non-empty")
        if not self.name.strip():
            raise ValueError("name must be non-empty")
        if self.mode is GoalMode.PROGRESSIVE:
            if self.ladder is None:
                raise ValueError("a progressive goal requires a level ladder")
            if self.lever_commitment_id is None:
                raise ValueError("a progressive goal requires a lever commitment")
        if self.mode is GoalMode.SEQUENCE:
            if self.terminal is None:
                raise ValueError("a sequence goal requires a terminal")
            if not self.steps:
                raise ValueError("a sequence goal requires a chain of lever steps")

    @property
    def ordered_steps(self) -> tuple[LeverStep, ...]:
        """The chain's steps in ascending order (the release order)."""
        return tuple(sorted(self.steps, key=lambda s: s.order))


__all__ = [
    "ControlAxis",
    "Goal",
    "GoalMode",
    "LevelLadder",
    "LeverStep",
    "StepState",
    "Subject",
    "Terminal",
    "TerminalState",
]
