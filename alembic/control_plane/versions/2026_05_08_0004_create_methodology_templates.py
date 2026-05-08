"""create methodology_templates and methodology_revisions

Revision ID: 0004_create_methodology_templates
Revises: 0003_add_cost_columns
Create Date: 2026-05-08

Methodology context's persistence schema lands on the control-plane
Postgres instance per D33. Two tables:

- ``methodology_templates``: human-stable identity for a methodology.
  Partial unique index on ``name`` where ``archived_at IS NULL``
  enforces unique active template names; archived templates retain
  their name without conflict for audit purposes per D31's append-
  only-at-version-level discipline.

- ``methodology_revisions``: per-version content plus the hash-chain
  pointers per D26 mirroring the audit-chain pattern. JSONB columns
  for the structured fields (``source_ids``, ``tool_allowlist``,
  ``retrieval_strategy``, ``filter_tree``); native columns for scalar
  fields. UNIQUE(methodology_template_id, version) prevents duplicate
  versions per template. Each template has its own chain rooted at
  the genesis sentinel ``"0" * 64``; chains are independent per
  template, mirroring the per-sheet revision pattern of
  ``scoring_sheet_revisions``.

JSONB convention follows the per-tenant ``0003_create_evaluation_tables``
precedent at ``scoring_sheet_criteria.levels``: bare ``pg.JSONB()`` per
the actual code precedent. The brief specified
``JSONB(astext_type=sa.Text())`` but the precedent file uses the bare
form; following actual code precedent per the structural-honesty test
at pre-write reconciliation. Mechanical deviation documented in the
S23 session log reflection.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0004_create_methodology_templates"
down_revision: Union[str, None] = "0003_add_cost_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "methodology_templates",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # Partial unique index on name where archived_at IS NULL: unique
    # active template names across the platform; archived templates
    # retain their name without conflict per D31's append-only
    # discipline.
    op.create_index(
        "ix_methodology_templates_name_unique_active",
        "methodology_templates",
        ["name"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
    )

    op.create_table(
        "methodology_revisions",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "methodology_template_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("methodology_templates.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("source_ids", pg.JSONB(), nullable=False),
        sa.Column("tool_allowlist", pg.JSONB(), nullable=False),
        sa.Column("retrieval_strategy", pg.JSONB(), nullable=False),
        sa.Column("filter_tree", pg.JSONB(), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("min_score", sa.Numeric(), nullable=False),
        sa.Column("model_selection", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("previous_revision_hash", sa.Text(), nullable=False),
        sa.Column("this_revision_hash", sa.Text(), nullable=False),
        sa.UniqueConstraint(
            "methodology_template_id",
            "version",
            name="methodology_revisions_template_version_unique",
        ),
    )


def downgrade() -> None:
    op.drop_table("methodology_revisions")
    op.drop_index(
        "ix_methodology_templates_name_unique_active",
        table_name="methodology_templates",
    )
    op.drop_table("methodology_templates")
