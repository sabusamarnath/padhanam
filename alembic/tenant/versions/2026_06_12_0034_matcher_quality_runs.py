"""matcher_quality_runs: the matcher-quality producer's per-run record

Revision ID: 0034_matcher_quality_runs
Revises: 0033_email_job_search_kind
Create Date: 2026-06-12

D185/S90. One row per matcher measurement — the structural quality of one
``correlate_goal_facets`` run, computed at the observe-only pre-replace hook and
persisted by the ``matcher_evaluation`` producer. The six counts are the source
of truth; the three rates are stored alongside for direct query. **Counts and
rates only** — no title, sender, subject, unit id, or any content; the producer
measures the *shape* of the matcher's output, never its contents (the D185
no-content guarantee). The optimization EvidenceContext reads these rows through
the producer's reader port (S91).

Per-tenant only per D32.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0034_matcher_quality_runs"
down_revision: Union[str, None] = "0033_email_job_search_kind"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "matcher_quality_runs",
        sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text, nullable=False),
        sa.Column(
            "computed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("edge_count", sa.Integer, nullable=False),
        sa.Column("unit_count", sa.Integer, nullable=False),
        sa.Column("orphan_count", sa.Integer, nullable=False),
        sa.Column("single_signal_count", sa.Integer, nullable=False),
        sa.Column("candidate_count", sa.Integer, nullable=False),
        sa.Column("confirmed_count", sa.Integer, nullable=False),
        sa.Column("single_signal_share", sa.Float, nullable=False),
        sa.Column("candidate_to_confirmed_ratio", sa.Float, nullable=False),
        sa.Column("orphan_rate", sa.Float, nullable=False),
    )
    op.create_index(
        "ix_matcher_quality_runs_tenant_time",
        "matcher_quality_runs",
        ["tenant_id", "computed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_matcher_quality_runs_tenant_time")
    op.drop_table("matcher_quality_runs")
