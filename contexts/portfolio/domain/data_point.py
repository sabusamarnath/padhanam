"""DataPoint — an entity within the Case aggregate (D124, D125).

A DataPoint is a goal, status, or methodology-application captured
against a Case. It carries an append-only revision history of
``Assertion`` instances and implements the Revisable Protocol
(D125) over ``Assertion``: ``revise`` appends a ``REVISION``
assertion and returns a new DataPoint; ``revision_history``
returns the chronological list; the current value is the latest
assertion's value.

DataPoint is frozen; ``revise`` produces a new instance. Protocol
conformance is structural — DataPoint does not inherit
``Revisable`` — and is exercised by the contract test per D114.

Domain code is framework-free per D16 — stdlib plus shared_kernel.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from shared_kernel import ActorReference, AssertionChange

from contexts.portfolio.domain.assertion import Assertion, AssertionType


class DataPointType(str, Enum):
    """DataPoint kind (D124)."""

    GOAL = "GOAL"
    STATUS = "STATUS"
    METHODOLOGY_APPLICATION = "METHODOLOGY_APPLICATION"


@dataclass(frozen=True)
class DataPoint:
    """A goal/status/methodology-application within a Case (D124).

    Implements ``Revisable[Assertion]`` per D125 structurally.
    """

    id: UUID
    case_id: UUID
    tenant_id: UUID
    jurisdiction: str
    data_point_type: DataPointType
    value: dict[str, Any]
    authored_by: ActorReference
    created_at: datetime
    assertions: tuple[Assertion, ...]
    certainty: float | None = None

    def __post_init__(self) -> None:
        if not self.jurisdiction.strip():
            raise ValueError("jurisdiction must be non-empty")
        if self.certainty is not None and not 0.0 <= self.certainty <= 1.0:
            raise ValueError(
                f"certainty must be in [0, 1]; got {self.certainty}"
            )
        if not self.assertions:
            raise ValueError(
                "DataPoint must carry at least one (INITIAL) assertion"
            )
        if self.assertions[0].assertion_type is not AssertionType.INITIAL:
            raise ValueError("the first assertion must be INITIAL")
        if any(
            a.assertion_type is not AssertionType.REVISION
            for a in self.assertions[1:]
        ):
            raise ValueError("every assertion after the first must be REVISION")

    @property
    def current_value(self) -> dict[str, Any]:
        """The current state — the latest assertion's value."""
        return self.assertions[-1].value

    def revise(
        self, change: AssertionChange, actor: ActorReference
    ) -> "DataPoint":
        """Append a REVISION assertion; return the extended DataPoint.

        Implements ``Revisable.revise`` per D125. The new assertion
        is minted here — id and timestamp — and chained to the prior
        head of the revision history via ``revises_assertion_id``.
        """
        revision = Assertion(
            id=uuid4(),
            data_point_id=self.id,
            tenant_id=self.tenant_id,
            jurisdiction=self.jurisdiction,
            assertion_type=AssertionType.REVISION,
            revises_assertion_id=self.assertions[-1].id,
            value=change.value,
            authored_by=actor,
            created_at=datetime.now(timezone.utc),
        )
        return replace(self, assertions=self.assertions + (revision,))

    def revision_history(self) -> list[Assertion]:
        """Return the full revision history in chronological order.

        Implements ``Revisable.revision_history`` per D125.
        """
        return list(self.assertions)


__all__ = ["DataPoint", "DataPointType"]
