"""add trace_id to rubric_applications

Revision ID: 0004_add_rubric_apps_trace_id
Revises: 0003_create_evaluation_tables
Create Date: 2026-05-06

The replay engine at S17a populates ``trace_id`` on every
``rubric_application`` it produces; the column links each scored
output to the trace that produced it (the OTel/Langfuse span the
LiteLLMAdapter emitted, with cost attributes on the same span). S17b
joins ``rubric_applications`` by ``trace_id`` to the trace store's
``gen_ai.cost.*`` attributes to compute cost-per-successful-task per
D8/D41, without coupling the evaluation harness to a specific trace
store implementation per D27.

Forward-affordance discipline (S16 reflection 4) held: trace_id is
landed alongside its proximate consumer (the replay engine). No
backfill against existing rows is required — the S16 integration
test truncates evaluation tables on each run, and no production data
exists at S17a. The column is nullable: rubric_applications produced
by paths that do not pass through the replay engine (deterministic
applier invoked from a flow that does not run a model) leave
trace_id null, and downstream cost queries skip those rows.

Adapter consumers per the S14 schema-tightening convention:
- ``contexts/evaluation/application/apply_scoring_sheet.py`` gains
  an optional ``trace_id: str | None = None`` parameter at S17a
  commit 5 and threads it through ``RubricApplication`` construction.
- ``contexts/evaluation/adapters/outbound/postgres/rubric_application_repository.py``
  picks up the new column in the same S17a commit 5 (no separate
  adapter touch needed; the SQLAlchemy Core table definition adds
  the column and the existing ``insert(...).values(...)`` call grows
  one keyword).
- The S16 ``apply_scoring_sheet`` callers (the e2e integration test)
  pass no ``trace_id`` and the column persists as null, exercising
  the backward-compatible default.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_add_rubric_apps_trace_id"
down_revision: Union[str, None] = "0003_create_evaluation_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "rubric_applications",
        sa.Column("trace_id", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("rubric_applications", "trace_id")
