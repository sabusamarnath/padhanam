"""create role_templates and role_revisions

Revision ID: 0005_role_tables
Revises: 0004_methodology_tables
Create Date: 2026-05-11

Role aggregate's persistence schema lands on the control-plane Postgres
instance per D33, alongside the methodology aggregate that hosts it
within `contexts/methodology/` per D86's Y2 sub-choice (role is first-
class within methodology context at Phase 1; promotion to its own
bounded context defers to Phase 2 if evidence demands). The shape
mirrors `0004_methodology_tables` exactly: two tables, the template
carrying human-stable identity, the revision carrying per-version
content plus hash-chain pointers per D26.

- ``role_templates``: human-stable identity for a role. Partial unique
  index on ``name`` where ``archived_at IS NULL`` mirrors the
  methodology_templates pattern.

- ``role_revisions``: per-version content plus the hash-chain pointers.
  Content fields match the prior methodology constraint bundle:
  system_prompt, source_ids (jsonb), tool_allowlist (jsonb),
  retrieval_strategy (jsonb), filter_tree (jsonb), top_k, min_score,
  model_selection. UNIQUE(role_template_id, version) prevents duplicate
  versions. Each template has its own chain rooted at the genesis
  sentinel ``"0" * 64``.

Per D86's idealization-versus-implementation reconciliation (recorded
in S26a-1's session log), the role bundle uses ``source_ids`` (matching
the prior methodology shape) and omits ``cost_ceiling``. D86's wording
named ``source_filter`` and ``cost_ceiling`` but Phase 1 implements with
existing field names to avoid introducing schema concepts without
consumers. Cost-ceiling forward-affordance already exists at the
tenant-registry level per D41 and is unread until Phase 2 enforcement.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0005_role_tables"
down_revision: Union[str, None] = "0004_methodology_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "role_templates",
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

    op.create_index(
        "ix_role_templates_name_unique_active",
        "role_templates",
        ["name"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
    )

    op.create_table(
        "role_revisions",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "role_template_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("role_templates.id"),
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
            "role_template_id",
            "version",
            name="role_revisions_template_version_unique",
        ),
    )


def downgrade() -> None:
    op.drop_table("role_revisions")
    op.drop_index(
        "ix_role_templates_name_unique_active",
        table_name="role_templates",
    )
    op.drop_table("role_templates")
