"""emails: persist the job-search classifier verdict (job_search_kind)

Revision ID: 0033_email_job_search_kind
Revises: 0032_target_cell_calendar_email
Create Date: 2026-06-12

D183/S89. The rules-only job-search classifier (sender/subject metadata) writes
its verdict here, on the email row, so it **persists** across recomputes: every
``correlate_goal_facets`` run replaces the whole tenant SERVES set, so the
Get-a-job email edges must be re-derivable from a durable source, not a one-run
artefact. ``job_search_kind`` is derived metadata (application / acknowledgement
/ interview / offer / rejection), not content — it sits with the plaintext
metadata columns (``received_at``, ``labels``), never the D21-encrypted content.
``NULL`` means not-a-job-search-email (or not yet classified); a re-run after
tightening the rules overwrites the column, so the edges follow the rules.

Per-tenant only per D32.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0033_email_job_search_kind"
down_revision: Union[str, None] = "0032_target_cell_calendar_email"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "emails",
        sa.Column("job_search_kind", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("emails", "job_search_kind")
