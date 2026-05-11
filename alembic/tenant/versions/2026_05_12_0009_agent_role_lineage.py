"""add role lineage to agent_templates

Revision ID: 0009_agent_role_lineage
Revises: 0008_agent_tables
Create Date: 2026-05-12

S26a-2 per-tenant schema extension per D86. The agent template gains
``source_role_id`` and ``source_role_version`` so the role-first model
records the role an agent occupies independently of the methodology
playbook that composed it. The new columns:

- Are paired-NULL via the new CHECK constraint
  ``agent_templates_role_lineage_paired_null`` (independent of D75's
  ``agent_templates_lineage_paired_null`` on the methodology pair).
- Are nullable for blank-created agents and for methodology-NULL +
  role-NULL audit histories that pre-date D86 (the migration produces
  no row whose role pair is partially populated).
- Are populated during this migration's backfill for existing rows
  that carry methodology lineage; the resolved role is the first
  ``role_refs`` entry of the methodology revision they cloned from,
  fetched from the control-plane Postgres.

The backfill crosses planes because methodology and role storage lives
on the control plane per D33 while agent storage is per-tenant per D32.
Migration imports ``ControlPlaneSettings`` and opens a one-shot sync
SQLAlchemy engine against the control plane to read role_refs for the
methodology revisions referenced by this tenant's clones. Three valid
post-migration states for the lineage pairs land per charter/schema.md
(both NULL, both pairs populated, only role pair populated); state
four — methodology populated and role NULL — cannot occur because the
backfill always resolves a role for methodology-populated rows and
S26a-1's 0006 migration guarantees every methodology revision has at
least one role_refs entry.

Down-migration drops the CHECK constraint and the two columns. The
backfill is not reversed because the methodology-cloned agents are
themselves unaffected by losing the role-lineage attribution
(methodology lineage on the same rows remains intact); the lossy
direction is the audit recovery path, not a routine operation.
"""
from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from padhanam.config import ControlPlaneSettings


revision: str = "0009_agent_role_lineage"
down_revision: Union[str, None] = "0008_agent_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_CHECK_NAME = "agent_templates_role_lineage_paired_null"


def _control_plane_url() -> str:
    s = ControlPlaneSettings()
    return (
        f"postgresql+psycopg://{s.user}:{s.password}@{s.host}:{s.port}/{s.db}"
    )


def _backfill_role_lineage() -> None:
    """Populate (source_role_id, source_role_version) on existing rows.

    For every agent template whose methodology lineage is set, read the
    referenced methodology revision's ``role_refs`` from the control
    plane and write the first entry's (role_id, role_version) onto the
    tenant row. Rows without methodology lineage stay paired-NULL on
    the role pair. The migration is a no-op when the tenant has no
    methodology-cloned agents.
    """
    tenant_bind = op.get_bind()
    rows = tenant_bind.execute(
        sa.text(
            """
            SELECT id,
                   source_methodology_template_id AS m_id,
                   source_methodology_template_version AS m_version
            FROM agent_templates
            WHERE source_methodology_template_id IS NOT NULL
            """
        )
    ).mappings().all()

    if not rows:
        return

    control_plane_engine = sa.create_engine(_control_plane_url())
    try:
        with control_plane_engine.connect() as cp_conn:
            for row in rows:
                m_id = row["m_id"]
                m_version = row["m_version"]
                revision_row = cp_conn.execute(
                    sa.text(
                        """
                        SELECT role_refs
                        FROM methodology_revisions
                        WHERE methodology_template_id = :template_id
                          AND version = :version
                        """
                    ),
                    {"template_id": str(m_id), "version": int(m_version)},
                ).mappings().first()
                if revision_row is None:
                    # The methodology revision the agent references no
                    # longer exists on the control plane; leave the
                    # role pair NULL. The audit-time integrity report
                    # will surface the dangling lineage.
                    continue
                raw_refs = revision_row["role_refs"]
                refs = (
                    raw_refs
                    if isinstance(raw_refs, list)
                    else json.loads(raw_refs)
                )
                if not refs:
                    continue
                first = refs[0]
                role_id = first.get("role_id")
                role_version = first.get("role_version")
                if role_id is None or role_version is None:
                    continue
                tenant_bind.execute(
                    sa.text(
                        """
                        UPDATE agent_templates
                        SET source_role_id = :role_id,
                            source_role_version = :role_version
                        WHERE id = :template_id
                        """
                    ),
                    {
                        "role_id": str(role_id),
                        "role_version": int(role_version),
                        "template_id": str(row["id"]),
                    },
                )
    finally:
        control_plane_engine.dispose()


def upgrade() -> None:
    op.add_column(
        "agent_templates",
        sa.Column(
            "source_role_id",
            pg.UUID(as_uuid=False),
            nullable=True,
        ),
    )
    op.add_column(
        "agent_templates",
        sa.Column(
            "source_role_version",
            sa.Integer(),
            nullable=True,
        ),
    )

    _backfill_role_lineage()

    op.create_check_constraint(
        _CHECK_NAME,
        "agent_templates",
        "(source_role_id IS NULL) = (source_role_version IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(_CHECK_NAME, "agent_templates", type_="check")
    op.drop_column("agent_templates", "source_role_version")
    op.drop_column("agent_templates", "source_role_id")
