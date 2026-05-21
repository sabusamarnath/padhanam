"""Revisable Protocol — cross-context append-only revision contract (D125, S43).

D114 committed the revision-with-lineage standard interface as a
Phase 2-A architectural primitive; this module commits its
concrete shape per D125.

``Revisable`` is the structural contract for any entity that
carries an append-only revision history: ``revise`` appends a new
revision rather than overwriting, the latest revision is the
entity's current state, and ``revision_history`` returns the full
list in chronological order.

The protocol is generic over the revision type ``RevisionT`` so it
imports no bounded-context type — ``shared_kernel/`` cannot import
``contexts/`` per D16, and the generic shape also surfaces the
protocol's job as "any entity with an append-only revision
history" rather than coupling it to one context's entity.
``contexts/portfolio/``'s ``DataPoint`` implements
``Revisable[Assertion]`` at S43; methodology-application revision
(P14) and Case-level revision are future implementers.

The procurement-grade specification surface is the "Cross-cutting
binding shapes" section of ``charter/schema.md``; this module is
the implementation surface.

Framework-free per D16 — shared_kernel is policed; stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, TypeVar, runtime_checkable

from shared_kernel.actor_reference import ActorReference

RevisionT = TypeVar("RevisionT")


@dataclass(frozen=True)
class AssertionChange:
    """The revision-input value object passed to ``Revisable.revise``.

    Carries the structured payload of the new revision. ``revise``
    consumes an ``AssertionChange`` plus an ``ActorReference`` and
    appends a revision carrying the change's ``value``.
    """

    value: dict[str, Any]

    def __post_init__(self) -> None:
        if self.value is None:  # type: ignore[redundant-expr]
            raise ValueError("AssertionChange.value must not be None")


@runtime_checkable
class Revisable(Protocol[RevisionT]):
    """Append-only revision-history contract (D114 primitive, D125 shape).

    An entity satisfies ``Revisable`` structurally — no explicit
    inheritance is required. The ``@runtime_checkable`` decorator
    additionally allows ``isinstance`` conformance checks, which the
    contract tests per D114 exercise.
    """

    def revise(
        self, change: AssertionChange, actor: ActorReference
    ) -> "Revisable[RevisionT]":
        """Append a revision; return the entity carrying extended history."""
        ...

    def revision_history(self) -> list[RevisionT]:
        """Return the full revision history in chronological order."""
        ...
