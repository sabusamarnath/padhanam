"""Rubric application domain entity (D53).

A ``RubricApplication`` is one criterion's score against one
interaction. Per D53, the record carries both ``automated_score`` and
``human_score`` from inception so the substrate for calibration learning
and the audit trail for human review both exist before the human-review
UI ships. P5 ships only the automated write path (deterministic and
prompt appliers populate ``automated_score``); ``human_score``,
``reviewed_by_user_id``, and ``confirmed_at`` stay null at S16 per the
Reading-C posture.

Score values are text per D55. Score interpretation is criterion-level:
each criterion's ``levels`` tuple defines what its scores mean.
Aggregation across rubric_applications requires criterion-level
filtering; direct ``AVG(automated_score)`` is foreclosed and is not the
intended access pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class RubricApplication:
    id: UUID
    scoring_sheet_revision_id: UUID
    criterion_id: UUID
    interaction_id: UUID
    applier_id: UUID
    automated_score: str | None
    human_score: str | None
    reviewed_by_user_id: str | None
    confirmed_at: datetime | None
    created_at: datetime
