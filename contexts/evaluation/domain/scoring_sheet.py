"""Scoring sheet domain entities (D53).

The scoring sheet is the user-facing primitive for evaluation per D53.
Three layered records, all frozen:

  - ``ScoringSheet`` is the named container with authorship metadata.
  - ``ScoringSheetRevision`` is an immutable per-version record. Updates
    create new revisions per D53; rubric_applications reference the
    revision id, not the sheet id, so historical evaluations stay
    anchored to the version they were applied against.
  - ``Criterion`` belongs to a revision and carries the levels that
    define what scores mean for it. Levels are domain data with explicit
    structure (level label + definition) so the criterion's score
    interpretation lives where the criterion is defined per D55.

Domain code is framework-free per D16 — stdlib dataclasses, no Pydantic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class CriterionLevel:
    """One level on a criterion.

    ``label`` is the score value applied to a rubric_application when
    this level is the chosen interpretation (e.g. ``"pass"``,
    ``"4"``, ``"0.85"``); ``definition`` is the human-readable
    description of what produces that level.
    """

    label: str
    definition: str


@dataclass(frozen=True)
class ScoringSheet:
    id: UUID
    name: str
    description: str
    created_by_user_id: str
    created_at: datetime
    archived_at: datetime | None = None


@dataclass(frozen=True)
class ScoringSheetRevision:
    id: UUID
    scoring_sheet_id: UUID
    version: int
    description: str
    created_by_user_id: str
    created_at: datetime


@dataclass(frozen=True)
class Criterion:
    id: UUID
    scoring_sheet_revision_id: UUID
    name: str
    description: str
    levels: tuple[CriterionLevel, ...]
    ordering: int
