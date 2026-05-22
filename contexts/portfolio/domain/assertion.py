"""Assertion — the append-only revision unit of the portfolio context (D124).

An Assertion is one entry in a DataPoint's revision history. The
first assertion of every DataPoint is ``INITIAL`` (created when the
DataPoint is created); every ``Revisable.revise`` call appends a
``REVISION`` assertion whose ``revises_assertion_id`` points at the
prior head of the chain. Assertions are never updated or deleted —
the append-only revision-with-lineage primitive per D114.

Domain code is framework-free per D16 — stdlib plus shared_kernel.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from shared_kernel import ActorReference


class AssertionType(str, Enum):
    """Assertion lifecycle position (D124)."""

    INITIAL = "INITIAL"
    REVISION = "REVISION"


@dataclass(frozen=True)
class Assertion:
    """One entry in a DataPoint's append-only revision history (D124).

    ``intake_id`` (D128) is the foreign key to the IntakeRecord this
    assertion traces to. Nullable at the domain layer: the
    intake-canonical orchestration path populates it; direct
    construction outside an orchestration leaves it ``None``.
    """

    id: UUID
    data_point_id: UUID
    tenant_id: UUID
    jurisdiction: str
    assertion_type: AssertionType
    revises_assertion_id: UUID | None
    value: dict[str, Any]
    authored_by: ActorReference
    created_at: datetime
    intake_id: UUID | None = None

    def __post_init__(self) -> None:
        if not self.jurisdiction.strip():
            raise ValueError("jurisdiction must be non-empty")
        if self.assertion_type is AssertionType.INITIAL:
            if self.revises_assertion_id is not None:
                raise ValueError(
                    "INITIAL assertion must not set revises_assertion_id"
                )
        else:
            if self.revises_assertion_id is None:
                raise ValueError(
                    "REVISION assertion must set revises_assertion_id"
                )


__all__ = ["Assertion", "AssertionType"]
