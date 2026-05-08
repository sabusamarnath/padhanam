"""create agent_templates and agent_revisions

Revision ID: 0008_agent_tables
Revises: 0007_extend_state_for_extraction
Create Date: 2026-05-08

Agent context's persistence schema lands on each tenant's dedicated
Postgres data plane per D32. Two tables:

- ``agent_templates``: human-stable identity for an agent plus the
  methodology lineage fields. Partial unique index on ``name`` where
  ``archived_at IS NULL`` enforces unique active agent names per
  tenant; archived templates retain their name without conflict for
  audit purposes per D31's append-only-at-version-level discipline.
  CHECK constraint ``agent_templates_lineage_paired_null`` enforces
  D75's paired-NULL invariant on the methodology lineage fields:
  either both NULL (blank-created agent at S24) or both populated
  (clone-created from a methodology template at S25's cross-context
  flow). Domain-layer enforcement via ``__post_init__`` provides
  defence-in-depth alongside this schema-layer constraint.

- ``agent_revisions``: per-version content plus the hash-chain
  pointers per D26 inheriting D74's audit-mirror shape. JSONB columns
  for the structured fields (``source_ids``, ``tool_allowlist``,
  ``retrieval_strategy``, ``filter_tree``); native columns for scalar
  fields. UNIQUE(agent_template_id, version) prevents duplicate
  versions per template. Each template has its own chain rooted at
  the genesis sentinel ``"0" * 64``; chains are independent per
  template, mirroring the methodology revision pattern from S23.

Per D75, ``name`` and ``description`` are read from the parent
``agent_templates`` row at hash-compute time and are not persisted as
columns on ``agent_revisions``; the canonical-JSON payload pulls them
from the template at hash-compute time. This mirrors the methodology
context's actual implementation from S23 rather than D74's
literal-denormalisation text.

JSONB convention follows the per-tenant
``0003_create_evaluation_tables`` precedent at
``scoring_sheet_criteria.levels`` and the methodology migration at
``0004_methodology_tables``: bare ``pg.JSONB()`` per the actual code
precedent.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0008_agent_tables"
down_revision: Union[str, None] = "0007_extend_state_for_extraction"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_templates",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "source_methodology_template_id",
            pg.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column(
            "source_methodology_template_version",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column("created_by_user_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True),
        # D75 paired-NULL invariant on methodology lineage fields:
        # either both NULL (blank-created agent) or both populated
        # (clone-created from a methodology template). Defence-in-
        # depth alongside the AgentTemplate dataclass's __post_init__
        # enforcement.
        sa.CheckConstraint(
            "(source_methodology_template_id IS NULL) = "
            "(source_methodology_template_version IS NULL)",
            name="agent_templates_lineage_paired_null",
        ),
    )

    # Partial unique index on name where archived_at IS NULL: unique
    # active agent names per tenant; archived templates retain their
    # name without conflict per D31's append-only discipline.
    op.create_index(
        "ix_agent_templates_name_unique_active",
        "agent_templates",
        ["name"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
    )

    op.create_table(
        "agent_revisions",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "agent_template_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("agent_templates.id"),
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
            "agent_template_id",
            "version",
            name="agent_revisions_template_version_unique",
        ),
    )


def downgrade() -> None:
    op.drop_table("agent_revisions")
    op.drop_index(
        "ix_agent_templates_name_unique_active",
        table_name="agent_templates",
    )
    op.drop_table("agent_templates")
